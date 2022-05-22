#!/bin/bash

bumpversion minor && git push && git push --tags

VERSION=v`cat VERSION | xargs`
gh release create $VERSION -n "Version $VERSION"