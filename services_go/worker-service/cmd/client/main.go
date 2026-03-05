package main

import (
	"encoding/json"
	"log"

	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/config"
	"github.com/hibiken/asynq"
)

func main() {
	cfg, _ := config.LoadConfig()

	// Create Asynq client
	redisOpt := asynq.RedisClientOpt{
		Addr: cfg.RedisAddr(),
		DB:   cfg.RedisDB,
	}
	client := asynq.NewClient(redisOpt)

	// Enqueue a manual key pre-population task
	payload, _ := json.Marshal(map[string]int{
		"count": 100,
	})

	task := asynq.NewTask("key:prepopulate", payload, asynq.Queue("db_tasks"))

	info, err := client.Enqueue(task)
	if err != nil {
		log.Fatalf("Failed to enqueue task: %v", err)
	}

	log.Printf("✅ Task enqueued successfully!")
	log.Printf("   Task ID: %s", info.ID)
	log.Printf("   Queue: %s", info.Queue)
}
