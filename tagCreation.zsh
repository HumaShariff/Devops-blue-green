#!/bin/zsh
# Simple script to print the current directory and list files
git tag -d deploy
git push origin -d deploy
git tag deploy
git push origin deploy
