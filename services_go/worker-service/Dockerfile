# Build stage
FROM golang:1.24-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git

# Set working directory for the parent structure
WORKDIR /app

# Copy entire services_go directory structure
COPY . .

# Set working directory to worker-service for build
WORKDIR /app/worker-service

# Download dependencies
RUN go mod download

# Build the application
# -ldflags="-s -w" strips debug info for smaller binary
# -trimpath removes file system paths from binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o worker-service ./cmd/worker

# Final stage - minimal runtime image
FROM alpine:latest

# Install ca-certificates for HTTPS requests
RUN apk --no-cache add ca-certificates

# Create non-root user
RUN addgroup -g 1000 -S worker && \
    adduser -u 1000 -S worker -G worker

WORKDIR /app

# Copy binary from builder (note: path changed due to WORKDIR in builder)
COPY --from=builder /app/worker-service/worker-service .

# Change ownership
RUN chown -R worker:worker /app

# Switch to non-root user
USER worker

# Run the application
CMD ["./worker-service"]
