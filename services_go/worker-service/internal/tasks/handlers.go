package tasks

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/kaziiriad/url-shortener-scalable/services_go/worker-service/internal/db"
	"github.com/hibiken/asynq"
)

// KeyPrepopulatePayload defines the task payload
type KeyPrepopulatePayload struct {
	Count int `json:"count"`
}

// HandleKeyPrepopulate handles the key pre-population task
func HandleKeyPrepopulate(pgDB *db.PostgresDB) asynq.HandlerFunc {
	return func(ctx context.Context, t *asynq.Task) error {
		var payload KeyPrepopulatePayload
		if err := json.Unmarshal(t.Payload(), &payload); err != nil {
			log.Printf("⚠️  Failed to unmarshal payload: %v", err)
			return fmt.Errorf("failed to unmarshal payload: %w", err)
		}

		count := payload.Count
		if count == 0 {
			// Use default from config if not specified
			count = 1000
		}

		log.Printf("🔑 Starting key pre-population: %d keys", count)

		inserted, err := pgDB.PrePopulateKeysHybrid(count)
		if err != nil {
			log.Printf("❌ Key pre-population failed: %v", err)
			return fmt.Errorf("key pre-population failed: %w", err)
		}

		log.Printf("✅ Key pre-population completed: %d keys inserted", inserted)
		return nil
	}
}

// RegisterTasks registers all task handlers with the Asynq server
func RegisterTasks(pgDB *db.PostgresDB) map[string]asynq.HandlerFunc {
	return map[string]asynq.HandlerFunc{
		"key:prepopulate": HandleKeyPrepopulate(pgDB),
	}
}

// EnqueueKeyPrepopulate enqueues a key pre-population task
func EnqueueKeyPrepopulate(client *asynq.Client, count int) error {
	payload, err := json.Marshal(KeyPrepopulatePayload{Count: count})
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	task := asynq.NewTask("key:prepopulate", payload)

	_, err = client.Enqueue(task)
	if err != nil {
		return fmt.Errorf("failed to enqueue task: %w", err)
	}

	log.Printf("📤 Enqueued key pre-population task: %d keys", count)
	return nil
}
