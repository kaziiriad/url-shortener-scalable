package repository

import (
	"context"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
)

type URLDoc struct {
	ID         bson.ObjectID `bson:"_id"`
	ShortURLID string        `bson:"short_url_id"`
	LongURL    string        `bson:"long_url"`
	ExpiresAt  *time.Time    `bson:"expires_at,omitempty"`
	CreatedAt  time.Time     `bson:"created_at"`
}

type MongoRepository struct {
	client     *mongo.Client
	collection *mongo.Collection
}

func NewMongoRepository(ctx context.Context, uri, dbName string) (*MongoRepository, error) {
	clientOptions := options.Client().ApplyURI(uri)
	newMongoClient, err := mongo.Connect(clientOptions)
	if err != nil {
		return nil, err
	}
	if err = newMongoClient.Ping(ctx, nil); err != nil {
		return nil, err
	}
	return &MongoRepository{
		client:     newMongoClient,
		collection: newMongoClient.Database(dbName).Collection("urls"),
	}, nil
}

func (m *MongoRepository) FindURLByShortKey(ctx context.Context, shortKey string) (*URLDoc, error) {

	filter := bson.D{{Key: "short_url_id", Value: shortKey}}
	result := m.collection.FindOne(ctx, filter)
	newDoc := URLDoc{}
	err := result.Decode(&newDoc)

	if err == mongo.ErrNoDocuments {
		// DEBUG: Log when document not found
		println("DEBUG: Document not found for key:", shortKey)
		return nil, mongo.ErrNoDocuments
	}

	if err != nil {
		// DEBUG: Log decode errors
		println("DEBUG: Decode error for key", shortKey, ":", err.Error())
		return nil, err
	}

	// DEBUG: Log success
	println("DEBUG: Found document for key:", shortKey, "URL:", newDoc.LongURL)
	return &newDoc, nil

}

func (m *MongoRepository) Close(ctx context.Context) error {
	return m.client.Disconnect(ctx)
}
