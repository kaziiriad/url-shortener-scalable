package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"redirect-service-go/internal/config"
	"redirect-service-go/internal/handler"
	"redirect-service-go/internal/repository"
	"redirect-service-go/internal/service"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
)

func main() {

	cfg, err := config.LoadConfig()

	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	log.Printf("Config loaded: %+v", cfg)

	redisRepo := repository.NewRedisRepository(
		fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		cfg.RedisMaxConnection,
	)

	mongoRepo, err := repository.NewMongoRepository(
		context.Background(),
		cfg.MongoURI,
		cfg.MongoDBName,
	)
	if err != nil {
		log.Fatalf("Failed to connect to MongoDB: %v", err)
	}
	defer mongoRepo.Close(context.Background())

	redirectService := service.NewRedirectService(
		redisRepo,
		mongoRepo,
	)

	h := handler.NewRedirectHandler(redirectService)
	r := chi.NewRouter()
	h.RegisterRoutes(r)

	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      r,
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		log.Printf("Starting server on port %d", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)

	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)

	defer cancel()

	server.Shutdown(ctx)

	log.Println("Server shutdown complete")

}
