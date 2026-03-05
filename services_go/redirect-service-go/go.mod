module github.com/kaziiriad/url-shortener-scalable/services_go/redirect-service-go

go 1.24

// Use local common module
replace github.com/kaziiriad/url-shortener-scalable/services_go/common => ../common

require (
	github.com/go-chi/chi/v5 v5.2.5
	github.com/kaziiriad/url-shortener-scalable/services_go/common v0.0.0-00010101000000-000000000000
	github.com/redis/go-redis/v9 v9.18.0
	go.mongodb.org/mongo-driver/v2 v2.5.0
)

require (
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
	github.com/google/go-cmp v0.7.0 // indirect
	github.com/joho/godotenv v1.5.1 // indirect
	github.com/klauspost/compress v1.17.6 // indirect
	github.com/stretchr/testify v1.11.1 // indirect
	github.com/xdg-go/pbkdf2 v1.0.0 // indirect
	github.com/xdg-go/scram v1.2.0 // indirect
	github.com/xdg-go/stringprep v1.0.4 // indirect
	github.com/youmark/pkcs8 v0.0.0-20240726163527-a2c0da244d78 // indirect
	go.uber.org/atomic v1.11.0 // indirect
	golang.org/x/crypto v0.33.0 // indirect
	golang.org/x/sync v0.16.0 // indirect
	golang.org/x/text v0.28.0 // indirect
)
