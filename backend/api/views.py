from django.shortcuts import render
from django.http import JsonResponse

def connection_test(request):
    return JsonResponse({"message": "Backend is online!"})
