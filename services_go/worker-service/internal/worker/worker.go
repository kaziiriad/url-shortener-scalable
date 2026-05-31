package worker

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/config"
	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/db"
	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/tasks"
	"github.com/hibiken/asynq"
)

// Worker manages the Asynq worker and scheduler
type Worker struct {
	config    *config.Config
	pgDB      *db.PostgresDB
	srv       *asynq.Server
	scheduler *asynq.Scheduler
	client    *asynq.Client
}

// NewWorker creates a new worker instance
func NewWorker(cfg *config.Config, pgDB *db.PostgresDB) *Worker {
	// Asynq Redis connection
	redisOpt := asynq.RedisClientOpt{
		Addr: cfg.RedisAddr(),
		DB:   cfg.RedisDB,
	}

	// Configure worker concurrency
	concurrency := cfg.Concurrency
	if concurrency < 1 {
		concurrency = 10
	}

	// Create server
	srv := asynq.NewServer(
		redisOpt,
		asynq.Config{
			Concurrency: concurrency,
			Queues: map[string]int{
				cfg.QueueName: 1, // Process db_tasks queue
			},
		},
	)

	// Create scheduler
	scheduler := asynq.NewScheduler(
		redisOpt,
		nil, // No special scheduler options needed
	)

	// Create client for enqueueing tasks
	client := asynq.NewClient(redisOpt)

	return &Worker{
		config:    cfg,
		pgDB:      pgDB,
		srv:       srv,
		scheduler: scheduler,
		client:    client,
	}
}

// Start starts the worker and scheduler
func (w *Worker) Start() error {
	// Register task handlers
	handlers := tasks.RegisterTasks(w.pgDB)
	mux := asynq.NewServeMux()
	for taskType, handler := range handlers {
		mux.Handle(taskType, handler)
		log.Printf("✅ Registered handler: %s", taskType)
	}

	// Register periodic task for key pre-population
	if err := w.registerPeriodicTasks(); err != nil {
		return err
	}

	// Start scheduler in background
	go func() {
		if err := w.scheduler.Run(); err != nil {
			log.Printf("❌ Scheduler error: %v", err)
		}
	}()
	log.Printf("✅ Scheduler started")

	// Start worker
	log.Printf("✅ Worker started (concurrency: %d, queue: %s)", w.config.Concurrency, w.config.QueueName)
	log.Printf("🔑 Key pre-population scheduled every %d seconds", w.config.KeyPopulationSchedule)

	return w.srv.Run(mux)
}

// registerPeriodicTasks registers scheduled tasks
func (w *Worker) registerPeriodicTasks() error {
	// Create payload for key pre-population
	payload, err := json.Marshal(tasks.KeyPrepopulatePayload{
		Count: w.config.KeyPopulationCount,
	})
	if err != nil {
		return err
	}

	// Register periodic task using standard cron syntax
	// Convert seconds to minutes (e.g., 300s → "*/5 * * * *")
	minutes := w.config.KeyPopulationSchedule / 60
	if minutes < 1 {
		minutes = 1 // Minimum 1 minute
	}
	cronSpec := fmt.Sprintf("*/%d * * * *", minutes)
	task := asynq.NewTask("key:prepopulate", payload, asynq.Queue(w.config.QueueName))

	if _, err := w.scheduler.Register(cronSpec, task); err != nil {
		return err
	}

	log.Printf("✅ Registered periodic task: %s (cron: %s)", "key:prepopulate", cronSpec)
	return nil
}

// Shutdown gracefully shuts down the worker
func (w *Worker) Shutdown() {
	log.Println("🛑 Shutting down worker...")

	w.scheduler.Shutdown()
	w.srv.Shutdown()
	w.pgDB.Close()
	w.client.Close()

	log.Println("✅ Worker shutdown complete")
}

// WaitForShutdown blocks until SIGINT or SIGTERM is received
func (w *Worker) WaitForShutdown() {
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
	<-sig
}
