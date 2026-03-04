package utils

import (
	"sync"
	"time"
)

type State string

const (
	StateClosed   State = "closed"
	StateOpen     State = "open"
	StateHalfOpen State = "half_open"
)

type CircuitBreaker struct {
	mu               sync.RWMutex
	state            State
	failures         int
	lastFailureTime  time.Time
	failureThreshold int
	timeout          time.Duration
}

func NewCircuitBreaker(failureThreshold int, timeout time.Duration) *CircuitBreaker {

	return &CircuitBreaker{
		state:            StateClosed,
		failureThreshold: failureThreshold,
		timeout:          timeout,
	}
}

func (cb *CircuitBreaker) CanExecute() bool {

	cb.mu.Lock()
	defer cb.mu.Unlock()

	state := cb.state
	if state == StateClosed || state == StateHalfOpen {
		return true
	}

	if state == StateOpen {
		if time.Since(cb.lastFailureTime) > cb.timeout {
			cb.state = StateHalfOpen
			return true
		}
		return false
	}
	return false
}

func (cb *CircuitBreaker) RecordSuccess() {

	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures = 0
	cb.state = StateClosed
}

func (cb *CircuitBreaker) RecordFailure() {

	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures++
	cb.lastFailureTime = time.Now()
	if cb.failures >= cb.failureThreshold {
		cb.state = StateOpen
	}

}

func (cb *CircuitBreaker) GetState() State {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}
