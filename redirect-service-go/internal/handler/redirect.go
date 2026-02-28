package handler

import (
	"encoding/json"
	"log"
	"net/http"

	"redirect-service-go/internal/service"

	"github.com/go-chi/chi/v5"
)

type RedirectHandler struct {
	service *service.RedirectService
}

func NewRedirectHandler(service *service.RedirectService) *RedirectHandler {
	return &RedirectHandler{service: service}
}

func (h *RedirectHandler) RegisterRoutes(r *chi.Mux) {
	r.Get("/", h.RootHandler)
	r.Get("/health", h.HealthHandler)
	r.Get("/{shortKey}", h.RedirectHandler)
}

func (h *RedirectHandler) RootHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"message": "Redirect Service",
		"status":  "running",
	})
}

func (h *RedirectHandler) HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "healthy",
		"service": "redirect_service",
	})
}

func (h *RedirectHandler) RedirectHandler(w http.ResponseWriter, r *http.Request) {

	shortKey := chi.URLParam(r, "shortKey")
	log.Printf("Request: method=%s path=%s key=%s", r.Method, r.URL.Path, shortKey)

	longUrl, err := h.service.GetLongURL(r.Context(), shortKey)

	if err != nil {
		if err.Error() == "circuit breaker open" {
			log.Printf("Response: key=%s status=503 circuit_breaker_open", shortKey)
			http.Error(w, "Service unavailable", http.StatusServiceUnavailable)
			return
		}
		if err.Error() == "key not found" {
			log.Printf("Response: key=%s status=404 not_found", shortKey)
			http.Error(w, "URL not found", http.StatusNotFound)
			return
		}

		log.Printf("Response: key=%s status=500 error=%v", shortKey, err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	if longUrl == "" {
		log.Printf("Response: key=%s status=404 expired", shortKey)
		http.Error(w, "URL not found", http.StatusNotFound)
		return
	}

	log.Printf("Response: key=%s status=301 redirect=%s", shortKey, longUrl)
	http.Redirect(w, r, longUrl, http.StatusMovedPermanently)

}
