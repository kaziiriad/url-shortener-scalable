package handler

import (
	"encoding/json"
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

	longUrl, err := h.service.GetLongURL(r.Context(), shortKey)

	if err != nil {
		if err.Error() == "circuit breaker open" {
			http.Error(w, "Service unavailable", http.StatusServiceUnavailable)
			return
		}
		if err.Error() == "key not found" {
			http.Error(w, "URL not found", http.StatusNotFound)
			return
		}

		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	if longUrl == "" {
		http.Error(w, "URL not found", http.StatusNotFound)
		return
	}

	http.Redirect(w, r, longUrl, http.StatusMovedPermanently)

}
