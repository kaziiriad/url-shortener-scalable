package service

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"redirect-service-go/internal/repository"
	"redirect-service-go/internal/utils"
	"time"

	"go.mongodb.org/mongo-driver/v2/mongo"
)

// Error definitions
var (
	ErrKeyNotFound         = errors.New("key not found")
	ErrCircuitBreakerOpen  = errors.New("circuit breaker open")
	ErrInternal            = errors.New("internal error")
)

type RedirectService struct {
	RedisRepo *repository.RedisRepository
	MongoRepo *repository.MongoRepository
	CB        *utils.CircuitBreaker
}

func NewRedirectService(
	redisRepo *repository.RedisRepository,
	mongoRepo *repository.MongoRepository,
) *RedirectService {

	return &RedirectService{
		RedisRepo: redisRepo,
		MongoRepo: mongoRepo,
		CB:        utils.NewCircuitBreaker(5, 60*time.Second),
	}
}

func (s *RedirectService) GetLongURL(ctx context.Context, shortKey string) (string, error) {
	log.Printf("Lookup: key=%s", shortKey)

	// check redis cache
	if cached, err := s.RedisRepo.Get(ctx, shortKey); err == nil && cached != "" {
		var urlDoc repository.URLDoc
		if err := json.Unmarshal([]byte(cached), &urlDoc); err != nil {
			log.Printf("Cache unmarshal error: key=%s error=%v", shortKey, err)
			return "", err
		}

		// check expiration
		if isExpired(urlDoc.ExpiresAt) {
			log.Printf("Cache expired: key=%s", shortKey)
			s.RedisRepo.Delete(ctx, shortKey)
			return "", nil
		}

		log.Printf("Cache hit: key=%s", shortKey)
		return urlDoc.LongURL, nil
	}

	log.Printf("Cache miss: key=%s", shortKey)

	// retrieve from mongodb with circuit breaker
	if !s.CB.CanExecute() {
		log.Printf("Circuit breaker open: key=%s", shortKey)
		return "", ErrCircuitBreakerOpen
	}

	urlDoc, err := s.MongoRepo.FindURLByShortKey(ctx, shortKey)
	if err == mongo.ErrNoDocuments {
		log.Printf("URL not found in DB: key=%s", shortKey)
		return "", ErrKeyNotFound
	}

	if err != nil {
		s.CB.RecordFailure()
		return "", err
	}
	s.CB.RecordSuccess()

	// check db expiration
	if keyExpired := isExpired(urlDoc.ExpiresAt); keyExpired {
		log.Printf("URL expired in DB: key=%s", shortKey)
		return "", nil
	}

	// cache in redis
	urlJSON, err := json.Marshal(urlDoc)
	if err != nil {
		return "", err
	}
	s.RedisRepo.Set(ctx, shortKey, string(urlJSON), 30*time.Minute)
	log.Printf("Cached: key=%s url=%s", shortKey, urlDoc.LongURL)
	return urlDoc.LongURL, nil
}

func isExpired(expiresAt *time.Time) bool {
	return expiresAt != nil && expiresAt.Before(time.Now())
}
