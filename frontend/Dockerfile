# Use the official Node.js 20 image.
FROM node:20-alpine

# Create and change to the app directory.
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install project dependencies.
RUN npm install

# Copy local files to the container.
COPY . .

# Build the app.
RUN npm run build

# Expose the port the app runs on.
EXPOSE 3000

# Run the app.
CMD ["npm", "start"] 