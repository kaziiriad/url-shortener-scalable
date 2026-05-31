package config

import (
	"fmt"

	"github.com/kaziiriad/url-shortener-scalable/services_go/common/env"
)

type Config struct {
	// Service configuration
	ServiceName string
	Environment string

	// MongoDB configuration
	MongoURI    string
	MongoDBName string

	// Redis configuration
	RedisHost     string
	RedisPort     int
	RedisPassword string
	RedisDB       int

	// PostgreSQL configuration
	PostgresHost     string
	PostgresPort     string
	PostgresUser     string
	PostgresPassword string
	PostgresDBName   string

	// Worker configuration
	Concurrency           int
	QueueName             string
	KeyPopulationCount    int
	KeyPopulationSchedule int // seconds

	// OpenTelemetry
	OTLPEndpoint   string
	TracingEnabled bool
}

func LoadConfig() (*Config, error) {
	env.LoadEnv()

	return &Config{
		// Service configuration
		ServiceName: env.GetString("SERVICE_NAME", "worker-service-go"),
		Environment: env.GetString("ENVIRONMENT", "development"),

		// MongoDB configuration
		MongoURI:    env.GetString("MONGO_URI", "mongodb://localhost:27017"),
		MongoDBName: env.GetString("MONGO_DB_NAME", "url_shortener"),

		// Redis configuration
		RedisHost:     env.GetString("REDIS_HOST", "localhost"),
		RedisPort:     env.GetInt("REDIS_PORT", 6379),
		RedisPassword: env.GetString("REDIS_PASSWORD", ""),
		RedisDB:       env.GetInt("REDIS_DB", 1),

		// PostgreSQL configuration
		PostgresHost:     env.GetString("POSTGRES_HOST", "localhost"),
		PostgresPort:     env.GetString("POSTGRES_PORT", "5432"),
		PostgresUser:     env.GetString("POSTGRES_USER", "postgres"),
		PostgresPassword: env.GetString("POSTGRES_PASSWORD", "pgpassword"),
		PostgresDBName:   env.GetString("POSTGRES_DB_NAME", "url_shortener"),

		// Worker configuration
		Concurrency:           env.GetInt("WORKER_CONCURRENCY", 10),
		QueueName:             env.GetString("WORKER_QUEUE", "db_tasks"),
		KeyPopulationCount:    env.GetInt("KEY_POPULATION_COUNT", 1000),
		KeyPopulationSchedule: env.GetInt("KEY_POPULATION_SCHEDULE", 300), // 5 minutes

		// OpenTelemetry
		OTLPEndpoint:   env.GetString("OTLP_ENDPOINT", "http://otel-collector:4317"),
		TracingEnabled: env.GetBool("TRACING_ENABLED", true),
	}, nil
}

// RedisAddr returns the Redis address in host:port format
func (c *Config) RedisAddr() string {
	return fmt.Sprintf("%s:%d", c.RedisHost, c.RedisPort)
}

// PostgresDSN returns the PostgreSQL connection string
func (c *Config) PostgresDSN() string {
	return fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		c.PostgresHost,
		c.PostgresPort,
		c.PostgresUser,
		c.PostgresPassword,
		c.PostgresDBName,
	)
}
