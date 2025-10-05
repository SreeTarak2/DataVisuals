#!/bin/bash

echo "🔑 Setting up OpenAI API Key for DataSage AI..."
echo ""

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "📝 Creating .env file from template..."
    cp backend/env.example backend/.env
    echo "✅ .env file created"
else
    echo "📝 .env file already exists"
fi

echo ""
echo "🔑 Please enter your OpenAI API key:"
echo "   (You can get this from https://platform.openai.com/api-keys)"
echo ""

read -p "OpenAI API Key: " openai_key

if [ -z "$openai_key" ]; then
    echo "❌ No API key provided. Please run this script again with a valid key."
    exit 1
fi

# Update the .env file
echo "📝 Updating .env file with your API key..."
sed -i "s/your_openai_api_key_here/$openai_key/g" backend/.env

echo ""
echo "✅ OpenAI API key configured successfully!"
echo ""
echo "🔍 To verify, check your .env file:"
echo "   cat backend/.env | grep OPENAI_API_KEY"
echo ""
echo "🚀 You can now start DataSage AI with:"
echo "   ./start.sh"
echo ""
echo "📚 For more setup instructions, see SETUP.md"
