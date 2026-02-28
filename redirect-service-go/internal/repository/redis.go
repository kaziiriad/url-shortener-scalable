package repository

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"
)

type RedisRepository struct {
	client *redis.Client
}

func NewRedisRepository(addr string, poolSize int) *RedisRepository {
	redisConn := &redis.Options{
		Addr:     addr,
		PoolSize: poolSize,
		DB:       0,
	}
	return &RedisRepository{
		client: redis.NewClient(redisConn),
	}
}

func (r *RedisRepository) Get(ctx context.Context, key string) (string, error) {

	val, err := r.client.Get(ctx, key).Result()

	if err == redis.Nil {
		return "", nil
	}
	if err != nil {
		return "", err
	}

	return val, nil
}

func (r *RedisRepository) Set(ctx context.Context, key string, value string, ttl time.Duration) error {

	return r.client.Set(ctx, key, value, ttl).Err()
}

func (r *RedisRepository) Delete(ctx context.Context, key string) error {
	return r.client.Del(ctx, key).Err()
}
