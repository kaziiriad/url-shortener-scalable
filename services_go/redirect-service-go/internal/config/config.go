package config

import (
	"github.com/kaziiriad/url-shortener-scalable/services_go/common/env"
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
	env.LoadEnv()

	return &Config{
		Port:               env.GetInt("PORT", 8001),
		ServiceName:        env.GetString("SERVICE_NAME", "redirect_service"),
		Environment:        env.GetString("ENVIRONMENT", "development"),
		MongoURI:           env.GetString("MONGO_URI", "mongodb://localhost:27017"),
		MongoDBName:        env.GetString("MONGO_DB_NAME", "url_shortener"),
		RedisHost:          env.GetString("REDIS_HOST", "localhost"),
		RedisPort:          env.GetInt("REDIS_PORT", 6379),
		RedisMaxConnection: env.GetInt("REDIS_MAX_CONNECTIONS", 10),
		OTLPEndpoint:       env.GetString("OTLP_ENDPOINT", "http://otel-collector:4317"),
		TracingEnabled:     env.GetBool("TRACING_ENABLED", true),
	}, nil
}
