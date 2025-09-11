import random
import sys
import time

print("Performing health check...")
time.sleep(1)

result = random.randint(0, 1)

if result == 0:
    print("Health check PASSED. Result: 0")
    sys.exit(0)
else:
    print("Health check FAILED. Result: 1")
    sys.exit(1)
