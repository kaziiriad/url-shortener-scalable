package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/config"
	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/db"
	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/worker"
)

func main() {
	log.Println("========================================")
	log.Println("🔑 Go Worker Service")
	log.Println("========================================")

	// Load configuration
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Fatalf("❌ Failed to load config: %v", err)
	}

	log.Printf("📋 Configuration:")
	log.Printf("   Service: %s", cfg.ServiceName)
	log.Printf("   Environment: %s", cfg.Environment)
	log.Printf("   Redis: %s (DB: %d)", cfg.RedisAddr(), cfg.RedisDB)
	log.Printf("   PostgreSQL: %s", cfg.PostgresHost)
	log.Printf("   Queue: %s", cfg.QueueName)
	log.Printf("   Concurrency: %d", cfg.Concurrency)
	log.Printf("   Key Pop Count: %d", cfg.KeyPopulationCount)
	log.Printf("   Key Pop Schedule: %d seconds", cfg.KeyPopulationSchedule)
	log.Println("========================================")

	// Connect to PostgreSQL
	pgDB, err := db.NewPostgresDB(cfg.PostgresDSN(), cfg.Concurrency*2)
	if err != nil {
		log.Fatalf("❌ Failed to connect to PostgreSQL: %v", err)
	}
	defer pgDB.Close()

	// Check current key count
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	totalKeys, err := pgDB.GetTotalKeyCount(ctx)
	if err != nil {
		log.Printf("⚠️  Could not get total key count: %v", err)
	} else {
		log.Printf("📊 Total keys in database: %d", totalKeys)
	}

	availableKeys, err := pgDB.GetAvailableKeyCount(ctx)
	if err != nil {
		log.Printf("⚠️  Could not get available key count: %v", err)
	} else {
		log.Printf("✅ Available keys: %d", availableKeys)
	}

	// Create and start worker
	w := worker.NewWorker(cfg, pgDB)

	// Handle graceful shutdown
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, os.Interrupt, syscall.SIGTERM)
		<-sig

		log.Println("🛑 Received shutdown signal")
		w.Shutdown()
		os.Exit(0)
	}()

	// Start the worker (blocking call)
	if err := w.Start(); err != nil {
		log.Fatalf("❌ Worker failed: %v", err)
	}
}
