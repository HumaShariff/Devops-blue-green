# Use a small JDK base image
FROM amazoncorretto:21-alpine

# Set working directory
WORKDIR /app

# Copy compiled classes (optional: compile inside Docker)
COPY build/ ./build
COPY src/AverageServer.java ./src/

# Compile Java app
RUN javac src/AverageServer.java -d build

# Expose the port your server uses
EXPOSE 8199

# Command to run the server
CMD ["java", "-cp", "build", "AverageServer"]

