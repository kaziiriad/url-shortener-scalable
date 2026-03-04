package config

import (
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	Port               int
	ServiceName        string
	Environment        string
	MongoURI           string
	MongoDBName        string
	RedisHost          string
	RedisPort          int
	RedisMaxConnection int
	OTLPEndpoint       string
	TracingEnabled     bool
}

func LoadConfig() (*Config, error) {
	// Try to load .env file, but don't fail if it doesn't exist
	// In Docker, environment variables are passed directly
	_ = godotenv.Load()

	return &Config{
		Port:               getInt("PORT", 8001),
		ServiceName:        getString("SERVICE_NAME", "redirect_service"),
		Environment:        getString("ENVIRONMENT", "development"),
		MongoURI:           getString("MONGO_URI", "mongodb://localhost:27017"),
		MongoDBName:        getString("MONGO_DB_NAME", "url_shortener"),
		RedisHost:          getString("REDIS_HOST", "localhost"),
		RedisPort:          getInt("REDIS_PORT", 6379),
		RedisMaxConnection: getInt("REDIS_MAX_CONNECTIONS", 10),
		OTLPEndpoint:       getString("OTLP_ENDPOINT", "http://otel-collector:4317"),
		TracingEnabled:     getBool("TRACING_ENABLED", true),
	}, nil
}

func getInt(key string, defaultVal int) int {
	if val := os.Getenv(key); val != "" {
		if parsed, err := strconv.Atoi(val); err == nil {
			return parsed
		}
	}
	return defaultVal
}

func getBool(key string, defaultVal bool) bool {
	if val := os.Getenv(key); val != "" {
		if parsed, err := strconv.ParseBool(val); err == nil {
			return parsed
		}
	}
	return defaultVal
}

func getString(key string, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}
