import os
import sys

# before any import — tests run without a GPU and without writing logs
os.environ["MOCK"] = "1"
os.environ["SAFETY_LOG"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
