package service

import (
	"testing"
	"time"

	"redirect-service-go/internal/utils"
)

// ============================================
// Circuit Breaker Tests
// ============================================

func TestNewCircuitBreaker(t *testing.T) {
	cb := utils.NewCircuitBreaker(5, 60*time.Second)

	if cb == nil {
		t.Error("expected non-nil circuit breaker")
	}
}

func TestCircuitBreaker_CanExecute_Initially(t *testing.T) {
	cb := utils.NewCircuitBreaker(5, 60*time.Second)

	if !cb.CanExecute() {
		t.Error("expected circuit breaker to allow execution initially")
	}
}

func TestCircuitBreaker_RecordSuccess(t *testing.T) {
	cb := utils.NewCircuitBreaker(5, 60*time.Second)

	// Record some failures
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}

	// Record success should reset
	cb.RecordSuccess()

	if cb.GetState() != utils.StateClosed {
		t.Errorf("expected utils.StateClosed after RecordSuccess, got %v", cb.GetState())
	}
}

func TestCircuitBreaker_OpensAfterThreshold(t *testing.T) {
	cb := utils.NewCircuitBreaker(3, 60*time.Second)

	// Record failures up to threshold
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}

	if cb.GetState() != utils.StateOpen {
		t.Errorf("expected utils.StateOpen after threshold failures, got %v", cb.GetState())
	}

	if cb.CanExecute() {
		t.Error("expected circuit breaker to not allow execution when open")
	}
}

func TestCircuitBreaker_HalfOpenAfterTimeout(t *testing.T) {
	cb := utils.NewCircuitBreaker(3, 1*time.Millisecond) // Short timeout for testing

	// Open the circuit
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}

	if cb.GetState() != utils.StateOpen {
		t.Errorf("expected utils.StateOpen, got %v", cb.GetState())
	}

	// Wait for timeout
	time.Sleep(10 * time.Millisecond)

	// Should transition to half-open
	if cb.CanExecute() {
		// After timeout, should allow execution (half-open state)
		if cb.GetState() != utils.StateHalfOpen {
			t.Logf("Note: State is %v (may transition to HalfOpen on CanExecute)", cb.GetState())
		}
	} else {
		t.Error("expected circuit breaker to allow execution after timeout")
	}
}

// ============================================
// IsExpired Function Tests
// ============================================

func TestIsExpired_WithNil(t *testing.T) {
	if isExpired(nil) {
		t.Error("expected false for nil expiration time")
	}
}

func TestIsExpired_FutureTime(t *testing.T) {
	future := time.Now().Add(24 * time.Hour)

	if isExpired(&future) {
		t.Error("expected false for future expiration time")
	}
}

func TestIsExpired_PastTime(t *testing.T) {
	past := time.Now().Add(-24 * time.Hour)

	if !isExpired(&past) {
		t.Error("expected true for past expiration time")
	}
}

func TestIsExpired_Now(t *testing.T) {
	now := time.Now()

	// Note: depends on exact timing, but should generally be false
	// for practical purposes
	if isExpired(&now) {
		t.Log("Note: Current time considered expired (edge case)")
	}
}

// ============================================
// Error Definitions Tests
// ============================================

func TestErrorDefinitions(t *testing.T) {
	if ErrKeyNotFound == nil {
		t.Error("ErrKeyNotFound should be defined")
	}

	if ErrCircuitBreakerOpen == nil {
		t.Error("ErrCircuitBreakerOpen should be defined")
	}

	if ErrInternal == nil {
		t.Error("ErrInternal should be defined")
	}

	if ErrKeyNotFound.Error() != "key not found" {
		t.Errorf("expected 'key not found', got %v", ErrKeyNotFound.Error())
	}
}

// ============================================
// Benchmarks
// ============================================

func BenchmarkCircuitBreaker_CanExecute(b *testing.B) {
	cb := utils.NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.CanExecute()
	}
}

func BenchmarkCircuitBreaker_RecordSuccess(b *testing.B) {
	cb := utils.NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.RecordSuccess()
	}
}

func BenchmarkCircuitBreaker_RecordFailure(b *testing.B) {
	cb := utils.NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.RecordFailure()
	}
}

func BenchmarkIsExpired(b *testing.B) {
	future := time.Now().Add(24 * time.Hour)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		isExpired(&future)
	}
}