#!/bin/bash

echo "creating a users directory..."
mkdir users
echo "creating a grades directory..."
mkdir grades
echo "creating an announcements directory..."
mkdir assignments
echo "creating a blank assignments file..."
touch assignments
echo "creating a default serverconfig.py..."
cp serverconfig.py.example serverconfig.py

echo "done"
