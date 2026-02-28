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

type RedirectService struct {
	redisRepo *repository.RedisRepository
	mongoRepo *repository.MongoRepository
	cb        *utils.CircuitBreaker
}

func NewRedirectService(
	redisRepo *repository.RedisRepository,
	mongoRepo *repository.MongoRepository,
) *RedirectService {

	return &RedirectService{
		redisRepo: redisRepo,
		mongoRepo: mongoRepo,
		cb:        utils.NewCircuitBreaker(5, 60*time.Second),
	}
}

func (s *RedirectService) GetLongURL(ctx context.Context, shortKey string) (string, error) {
	log.Printf("Lookup: key=%s", shortKey)

	// check redis cache
	if cached, err := s.redisRepo.Get(ctx, shortKey); err == nil && cached != "" {
		var urlDoc repository.URLDoc
		if err := json.Unmarshal([]byte(cached), &urlDoc); err != nil {
			log.Printf("Cache unmarshal error: key=%s error=%v", shortKey, err)
			return "", err
		}

		// check expiration
		if isExpired(urlDoc.ExpiresAt) {
			log.Printf("Cache expired: key=%s", shortKey)
			s.redisRepo.Delete(ctx, shortKey)
			return "", nil
		}

		log.Printf("Cache hit: key=%s", shortKey)
		return urlDoc.LongURL, nil
	}

	log.Printf("Cache miss: key=%s", shortKey)

	// retrieve from mongodb with circuit breaker
	if !s.cb.CanExecute() {
		log.Printf("Circuit breaker open: key=%s", shortKey)
		return "", errors.New("circuit breaker open")
	}

	urlDoc, err := s.mongoRepo.FindURLByShortKey(ctx, shortKey)
	if err == mongo.ErrNoDocuments {
		log.Printf("URL not found in DB: key=%s", shortKey)
		return "", errors.New("key not found")
	}

	if err != nil {
		s.cb.RecordFailure()
		return "", err
	}
	s.cb.RecordSuccess()

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
	s.redisRepo.Set(ctx, shortKey, string(urlJSON), 30*time.Minute)
	log.Printf("Cached: key=%s url=%s", shortKey, urlDoc.LongURL)
	return urlDoc.LongURL, nil
}

func isExpired(expiresAt *time.Time) bool {
	return expiresAt != nil && expiresAt.Before(time.Now())
}
