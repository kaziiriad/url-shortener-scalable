package utils

import (
	"testing"
	"time"
)

// ============================================
// Circuit Breaker State Tests
// ============================================

func TestNewCircuitBreaker(t *testing.T) {
	cb := NewCircuitBreaker(5, 60*time.Second)

	if cb == nil {
		t.Error("expected non-nil circuit breaker")
	}

	if cb.GetState() != StateClosed {
		t.Errorf("expected StateClosed initially, got %v", cb.GetState())
	}
}

func TestCircuitBreaker_StateTransitions(t *testing.T) {
	cb := NewCircuitBreaker(3, 100*time.Millisecond)

	// Initially closed
	if cb.GetState() != StateClosed {
		t.Errorf("expected StateClosed initially, got %v", cb.GetState())
	}

	// Open after threshold
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}

	if cb.GetState() != StateOpen {
		t.Errorf("expected StateOpen after failures, got %v", cb.GetState())
	}

	// Reset on success
	cb.RecordSuccess()

	if cb.GetState() != StateClosed {
		t.Errorf("expected StateClosed after RecordSuccess, got %v", cb.GetState())
	}
}

func TestCircuitBreaker_FailureThreshold(t *testing.T) {
	tests := []struct {
		name              string
		failureThreshold  int
		failures          int
		expectedCanExecute bool
	}{
		{"Below threshold", 5, 3, true},
		{"At threshold", 5, 5, false},
		{"Above threshold", 5, 10, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cb := NewCircuitBreaker(tt.failureThreshold, 60*time.Second)

			for i := 0; i < tt.failures; i++ {
				cb.RecordFailure()
			}

			result := cb.CanExecute()
			if result != tt.expectedCanExecute {
				t.Errorf("expected CanExecute=%v after %d failures (threshold=%d), got %v",
					tt.expectedCanExecute, tt.failures, tt.failureThreshold, result)
			}
		})
	}
}

func TestCircuitBreaker_HalfOpenTransition(t *testing.T) {
	cb := NewCircuitBreaker(3, 10*time.Millisecond)

	// Open the circuit
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}

	if cb.GetState() != StateOpen {
		t.Errorf("expected StateOpen, got %v", cb.GetState())
	}

	// Wait for timeout
	time.Sleep(15 * time.Millisecond)

	// CanExecute should transition to HalfOpen
	if !cb.CanExecute() {
		t.Error("expected CanExecute to return true after timeout (HalfOpen transition)")
	}

	// State should now be HalfOpen or Closed (depending on implementation)
	state := cb.GetState()
	if state != StateHalfOpen && state != StateClosed {
		t.Errorf("expected StateHalfOpen or StateClosed after CanExecute with timeout, got %v", state)
	}
}

func TestCircuitBreaker_ConcurrentAccess(t *testing.T) {
	cb := NewCircuitBreaker(100, 60*time.Second)

	// Simulate concurrent access
	done := make(chan bool)

	for i := 0; i < 10; i++ {
		go func() {
			for j := 0; j < 10; j++ {
				cb.CanExecute()
				cb.RecordSuccess()
			}
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	// Circuit breaker should still be in a valid state
	state := cb.GetState()
	if state != StateClosed {
		t.Logf("Note: State is %v after concurrent access", state)
	}
}

// ============================================
// Benchmarks
// ============================================

func BenchmarkCircuitBreaker_CanExecute(b *testing.B) {
	cb := NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.CanExecute()
	}
}

func BenchmarkCircuitBreaker_RecordSuccess(b *testing.B) {
	cb := NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.RecordSuccess()
	}
}

func BenchmarkCircuitBreaker_RecordFailure(b *testing.B) {
	cb := NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.RecordFailure()
	}
}

func BenchmarkCircuitBreaker_GetState(b *testing.B) {
	cb := NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		cb.GetState()
	}

	// Prevent compiler optimization
	if cb.GetState() == StateOpen {
		b.ResetTimer()
	}
}

func BenchmarkCircuitBreaker_FullCycle(b *testing.B) {
	cb := NewCircuitBreaker(5, 60*time.Second)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		if cb.CanExecute() {
			cb.RecordSuccess()
		} else {
			cb.RecordFailure()
		}
	}
}