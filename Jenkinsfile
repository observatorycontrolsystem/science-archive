#!/usr/bin/env groovy

@Library('lco-shared-libs@0.1.1') _

pipeline {
	agent any
	stages {
		stage('Build') {
			steps {
				sh 'make docker-build'
			}
		}
		stage('Push image') {
			steps {
				sh 'make docker-push'
			}
		}
	}
}
