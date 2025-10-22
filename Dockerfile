# Use lightweight Java runtime
FROM eclipse-temurin:21-jre-alpine

# Set working directory
WORKDIR /app

# Copy compiled class files
COPY ../build/ /app/

# Expose the server port
EXPOSE 8199

# Run the server
CMD ["java", "-cp", "/app", "AverageServer"]

