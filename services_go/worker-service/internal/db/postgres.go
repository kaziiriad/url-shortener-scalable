package db

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"math/rand"
	"time"

	_ "github.com/lib/pq"
)

// PostgresDB holds the PostgreSQL connection pool
type PostgresDB struct {
	*sql.DB
}

// NewPostgresDB creates a new PostgreSQL connection pool
func NewPostgresDB(dsn string, maxOpenConns int) (*PostgresDB, error) {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Set connection pool settings
	db.SetMaxOpenConns(maxOpenConns)
	db.SetMaxIdleConns(maxOpenConns / 2)
	if maxOpenConns < 2 {
		db.SetMaxIdleConns(1)
	}

	// Verify connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	log.Printf("✅ PostgreSQL connected (pool: %d max conns)", maxOpenConns)

	return &PostgresDB{DB: db}, nil
}

// PrePopulateKeysHybrid chooses the best strategy based on count
// - Small batches (<1K): Use single INSERT with Go-generated keys
// - Medium batches (1K-50K): Use single INSERT (fast, memory efficient)
// - Large batches (>50K): Use PostgreSQL native (fastest)
func (db *PostgresDB) PrePopulateKeysHybrid(count int) (int, error) {
	if count <= 0 {
		return 0, nil
	}

	log.Printf("Pre-populating %d keys using hybrid strategy", count)

	if count < 1000 {
		// Small batches: Go-generated keys with single INSERT
		return db.prePopulateKeysSingleInsert(count)
	} else if count < 50000 {
		// Medium batches: single INSERT
		return db.prePopulateKeysSingleInsert(count)
	} else {
		// Large batches: PostgreSQL native
		return db.prePopulateKeysPostgresNative(count)
	}
}

// prePopulateKeysSingleInsert generates keys in Go and inserts with single query
// Performance: ~100K keys in 2-3 seconds
func (db *PostgresDB) prePopulateKeysSingleInsert(count int) (int, error) {
	keys, err := generateKeys(count)
	if err != nil {
		return 0, fmt.Errorf("failed to generate keys: %w", err)
	}

	query := `
		INSERT INTO urls (key, is_used)
		VALUES ` + buildValuesClause(keys) + `
		ON CONFLICT (key) DO NOTHING
		RETURNING id
	`

	result, err := db.Exec(query)
	if err != nil {
		return 0, fmt.Errorf("failed to insert keys: %w", err)
	}

	insertedCount, _ := result.RowsAffected()
	log.Printf("✅ Inserted %d keys using single INSERT", insertedCount)
	return int(insertedCount), nil
}

// prePopulateKeysPostgresNative uses PostgreSQL's generate_series
// Performance: ~100K keys in 1-2 seconds (O(1) from app perspective)
func (db *PostgresDB) prePopulateKeysPostgresNative(count int) (int, error) {
	query := `
		INSERT INTO urls (key, is_used)
		SELECT
			substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) ||
				substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) ||
				substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) ||
				substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) ||
				substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) ||
				substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) ||
				substr('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789',
				(random() * 61 + 1)::int, 1) as key,
			false as is_used
		FROM generate_series(1, $1)
		ON CONFLICT (key) DO NOTHING
		RETURNING id
	`

	result, err := db.Exec(query, count)
	if err != nil {
		return 0, fmt.Errorf("failed to insert keys (postgres native): %w", err)
	}

	insertedCount, _ := result.RowsAffected()
	log.Printf("✅ Inserted %d keys using PostgreSQL native method", insertedCount)
	return int(insertedCount), nil
}

// GetUnusedKey atomically acquires an unused key using SELECT FOR UPDATE SKIP LOCKED
// This prevents race conditions in distributed systems
func (db *PostgresDB) GetUnusedKey(ctx context.Context) (string, error) {
	tx, err := db.BeginTx(ctx, &sql.TxOptions{})
	if err != nil {
		return "", fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	var key string
	err = tx.QueryRowContext(ctx, `
		SELECT key FROM urls
		WHERE is_used = false
		LIMIT 1
		FOR UPDATE SKIP LOCKED
	`,).Scan(&key)

	if err == sql.ErrNoRows {
		return "", fmt.Errorf("no unused keys available")
	}
	if err != nil {
		return "", fmt.Errorf("failed to acquire key: %w", err)
	}

	// Mark the key as used
	_, err = tx.ExecContext(ctx, `
		UPDATE urls
		SET is_used = true
		WHERE key = $1
	`, key)
	if err != nil {
		return "", fmt.Errorf("failed to mark key as used: %w", err)
	}

	if err := tx.Commit(); err != nil {
		return "", fmt.Errorf("failed to commit transaction: %w", err)
	}

	log.Printf("✅ Acquired key: %s", key)
	return key, nil
}

// GetAvailableKeyCount returns the count of available unused keys
func (db *PostgresDB) GetAvailableKeyCount(ctx context.Context) (int, error) {
	var count int
	err := db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM urls WHERE is_used = false
	`).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get available key count: %w", err)
	}
	return count, nil
}

// GetTotalKeyCount returns the total count of keys
func (db *PostgresDB) GetTotalKeyCount(ctx context.Context) (int, error) {
	var count int
	err := db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM urls
	`).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to get total key count: %w", err)
	}
	return count, nil
}

// Close closes the database connection
func (db *PostgresDB) Close() error {
	return db.DB.Close()
}

// Helper functions

// Initialize random seed
func init() {
	rand.Seed(time.Now().UnixNano())
}

// generateKeys generates random alphanumeric keys
func generateKeys(count int) ([]string, error) {
	keys := make([]string, count)
	for i := 0; i < count; i++ {
		key, err := generateKey()
		if err != nil {
			return nil, err
		}
		keys[i] = key
	}
	return keys, nil
}

// generateKey generates a single random 7-character alphanumeric key
func generateKey() (string, error) {
	const charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
	const keyLength = 7

	key := make([]byte, keyLength)
	for i := range key {
		key[i] = charset[rand.Intn(len(charset))]
	}
	return string(key), nil
}

// buildValuesClause builds a VALUES clause for SQL INSERT
// Example: ('key1', false), ('key2', false), ...
func buildValuesClause(keys []string) string {
	if len(keys) == 0 {
		return ""
	}

	var values string
	for i, key := range keys {
		if i > 0 {
			values += "),("
		}
		// Escape single quotes in key
		escaped := ""
		for _, ch := range key {
			if ch == '\'' {
				escaped += "''"
			} else {
				escaped += string(ch)
			}
		}
		values += "'" + escaped + "', false"
	}

	return "(" + values + ")"
}
