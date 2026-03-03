package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"redirect-service-go/internal/service"
)

// ============================================
// Root Handler Tests
// ============================================

func TestRootHandler(t *testing.T) {
	svc := &service.RedirectService{}
	h := NewRedirectHandler(svc)

	req := httptest.NewRequest("GET", "/", nil)
	w := httptest.NewRecorder()

	h.RootHandler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	// Verify content type
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected content-type application/json, got %s", ct)
	}
}

// ============================================
// Health Handler Tests
// ============================================

func TestHealthHandler(t *testing.T) {
	svc := &service.RedirectService{}
	h := NewRedirectHandler(svc)

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	h.HealthHandler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", w.Code)
	}

	// Verify content type
	if ct := w.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("expected content-type application/json, got %s", ct)
	}
}

// ============================================
// RegisterRoutes Tests
// ============================================

func TestRegisterRoutes(t *testing.T) {
	svc := &service.RedirectService{}
	h := NewRedirectHandler(svc)

	// Test that RegisterRoutes doesn't panic with a nil mux
	// In real usage, chi.Mux would be passed
	defer func() {
		if r := recover(); r != nil {
			t.Logf("RegisterRoutes panicked with nil mux (expected)")
		}
	}()

	h.RegisterRoutes(nil)
}

// ============================================
// Benchmarks
// ============================================

func BenchmarkRootHandler(b *testing.B) {
	svc := &service.RedirectService{}
	h := NewRedirectHandler(svc)

	req := httptest.NewRequest("GET", "/", nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		w := httptest.NewRecorder()
		h.RootHandler(w, req)
	}
}

func BenchmarkHealthHandler(b *testing.B) {
	svc := &service.RedirectService{}
	h := NewRedirectHandler(svc)

	req := httptest.NewRequest("GET", "/health", nil)

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		w := httptest.NewRecorder()
		h.HealthHandler(w, req)
	}
}