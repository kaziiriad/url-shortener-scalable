# Build stage
FROM golang:1.24-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Copy go mod files first (for caching)
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the application
# -ldflags="-s -w" strips debug info for smaller binary
# -trimpath removes file system paths from binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o redirect-service ./cmd/server

# Final stage - minimal runtime image
FROM alpine:latest

# Install ca-certificates for HTTPS requests
RUN apk --no-cache add ca-certificates

# Create non-root user
RUN addgroup -g 1000 -S redirect && \
    adduser -u 1000 -S redirect -G redirect

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/redirect-service .

# Change ownership
RUN chown -R redirect:redirect /app

# Switch to non-root user
USER redirect

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8001/health || exit 1

# Run the application
CMD ["./redirect-service"]
