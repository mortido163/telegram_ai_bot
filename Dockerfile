FROM ubuntu:latest
LABEL authors="dmitrij"

ENTRYPOINT ["top", "-b"]