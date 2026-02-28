package service

import (
	"context"
	"encoding/json"
	"errors"
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

	// check redis cache
	if cached, err := s.redisRepo.Get(ctx, shortKey); err == nil && cached != "" {
		var urlDoc repository.URLDoc
		if err := json.Unmarshal([]byte(cached), &urlDoc); err != nil {
			return "", err
		}

		// check expiration
		if isExpired(urlDoc.ExpiresAt) {
			s.redisRepo.Delete(ctx, shortKey)
			return "", nil
		}

		return urlDoc.LongURL, nil
	}

	// retrieve from mongodb with circuit breaker
	if !s.cb.CanExecute() {
		return "", errors.New("circuit breaker open")
	}

	urlDoc, err := s.mongoRepo.FindURLByShortKey(ctx, shortKey)
	if err == mongo.ErrNoDocuments {
		return "", errors.New("key not found")
	}

	if err != nil {
		s.cb.RecordFailure()
		return "", err
	}
	s.cb.RecordSuccess()

	// check db expiration
	if keyExpired := isExpired(urlDoc.ExpiresAt); keyExpired {
		return "", nil
	}

	// cache in redis
	urlJSON, err := json.Marshal(urlDoc)
	if err != nil {
		return "", err
	}
	s.redisRepo.Set(ctx, shortKey, string(urlJSON), 30*time.Minute)
	return urlDoc.LongURL, nil
}

func isExpired(expiresAt *time.Time) bool {
	return expiresAt != nil && expiresAt.Before(time.Now())
}
