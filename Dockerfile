# Use Alpine Linux as base image for minimal size
FROM alpine:3.19

# Install the necessary dependencies
RUN apk update && \
    apk add --no-cache \
    python3 \
    py3-pip \
    ghostscript \
    curl \
    bash

# Set the working directory
WORKDIR /app

# Create and activate a virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Upgrade pip inside the virtual environment
RUN pip install --upgrade pip

# Copy the requirements file and install dependencies inside the virtual environment
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application files
COPY main.py .

# Expose port 8000 for the API
EXPOSE 8000

# Start the API using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
