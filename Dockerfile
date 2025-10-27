# Use lightweight Java runtime
FROM amazoncorretto:21-alpine

# Set working directory
WORKDIR /app

# Copy compiled classes
COPY build/ build/
COPY src/ src/

# Expose the port
EXPOSE 8199

# Run the Java server
CMD ["java", "-cp", "build", "AverageServer"]

