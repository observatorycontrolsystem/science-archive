DOCKER_IMG := docker.lco.global/archive

GIT_DIRTY := $(shell git status --porcelain)
GIT_TAG := $(shell git describe --always)

HELM_CHART := lco/archiveapi

# Add a suffix to the tag if the repo is dirty
ifeq ($(GIT_DIRTY),)
TAG := $(GIT_TAG)
else
TAG := $(GIT_TAG)-dirty
endif

all: docker-build docker-push

docker-build:
	docker build --target app -t $(DOCKER_IMG):$(TAG) .

docker-push:
	docker push $(DOCKER_IMG):$(TAG)

dev-deploy:
	helm upgrade \
		--install \
		--namespace dev \
		--values deploy/dev-values.yaml \
		--wait \
		--set backend.image.tag=$(TAG) \
		archiveapi-dev \
		$(HELM_CHART)

prod-deploy:
	helm upgrade \
		--install \
		--namespace prod \
		--values deploy/prod-values.yaml \
		--wait \
		--set backend.image.tag=$(TAG) \
		archiveapi \
		$(HELM_CHART)
