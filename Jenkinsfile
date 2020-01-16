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
		stage('Integration tests') {
			steps {
				lock('archiveIt') {
					sh 'make integration-tests'
				}
			}
		}
		stage('Push image') {
			steps {
				sh 'make docker-push'
			}
		}
	}
}
