# Full-Stack Software System with CI/CD and Blue-Green Deployment

This repository contains an **individually implemented academic project** developed as part of the
*M.Sc. Software, Web, and Cloud* program at **Tampere University**.

The project demonstrates **end-to-end software development**, including application design,
automated testing, CI/CD pipelines, containerized deployment, monitoring, and secure access.

---

## Project Overview

The system is a **multi-service software application** consisting of:

- Backend REST API
- API Gateway (Nginx)
- Management & Monitoring Web UI
- Logging and monitoring components

The application supports **blue–green deployment**, allowing safe switching between two software
versions without downtime.

Two versions of the system are maintained:
- `project1.0`
- `project1.1`

---

## Architecture

The application is composed of multiple containerized services orchestrated using Docker Compose:

- **API Service** – Provides REST endpoints for application status and logs
- **API Gateway** – Handles HTTPS, authentication, and traffic routing between versions
- **Management Console** – Web-based UI for monitoring and controlling deployments
- **Monitoring Service** – Collects uptime, resource usage, and system metrics
- **Logging Service** – Maintains persistent logs across redeployments

---

## Key Features

- **Multi-service software architecture**
- **REST APIs** with secure access
- **Web-based management and monitoring UI**
- **Blue–green deployment strategy**
- **Automated CI/CD pipeline**
- **Containerized deployment using Docker**
- **Linux-based cloud deployment**

---

## CI/CD Pipeline

The project uses **GitLab CI/CD** with the following stages:

1. **Build** – Compile and prepare application artifacts
2. **Test** – Execute automated tests
3. **Package** – Build Docker images
4. **Smoke Test** – Verify container startup and basic functionality
5. **Deploy** – Deploy containers to a Linux cloud VM

Security best practices are followed using:
- Masked CI/CD variables
- SSH key-based authentication
- Container registry for image storage

---

## Deployment

The application is deployed on a **Linux cloud virtual machine** with a public IP address.

Deployment includes:
- Automated installation of Docker and Docker Compose
- Secure image retrieval from a container registry
- Persistent logging across redeployments
- Network and port configuration for public access

---

## Branches

- `project1.0` – Initial stable version
- `project1.1` – Updated version with enhanced behavior and metrics

Branch switching combined with the API gateway enables **blue–green deployment**.

---

## Technologies Used

- **Languages:** Python, C/C++
- **Containerization:** Docker, Docker Compose
- **CI/CD:** GitLab CI/CD
- **Web & Gateway:** Nginx, HTTPS/TLS
- **Systems:** Linux, Cloud VM
- **Monitoring & Debugging:** Logs, metrics, container inspection

---

## Learning Outcomes

Through this project, I gained hands-on experience in:

- Designing and implementing multi-service software systems
- Writing and validating automated tests
- Debugging runtime and deployment issues
- Building and maintaining CI/CD pipelines
- Deploying and operating applications in a Linux cloud environment
- Applying blue–green deployment strategies

---

## Notes

This project was completed **individually** as part of an academic course.
All design, implementation, deployment, and documentation were done by the author.

