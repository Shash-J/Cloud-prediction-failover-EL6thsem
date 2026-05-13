import multiprocessing
import time
import math
import argparse

def cpu_stress(duty_cycle=1.0):
    """
    Consumes CPU cycles. duty_cycle specifies the fraction of time to work vs sleep.
    1.0 means 100% CPU usage for this thread.
    """
    while True:
        if duty_cycle < 1.0:
            start_time = time.time()
            # Do work for duty_cycle * 0.1 seconds
            while time.time() - start_time < (duty_cycle * 0.1):
                _ = math.sqrt(64 * 64 * 64 * 64 * 64)
            # Sleep for the rest
            time.sleep((1.0 - duty_cycle) * 0.1)
        else:
             _ = math.sqrt(64 * 64 * 64 * 64 * 64)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Stress test an EC2 instance.")
    parser.add_argument('--cpu', action='store_true', help="Run immediate maximum CPU stress test")
    parser.add_argument('--gradual', action='store_true', help="Slowly increase CPU load over time")
    
    args = parser.parse_args()
    
    processes = []
    
    try:
        num_cores = multiprocessing.cpu_count()
        if args.cpu:
            print(f"Starting Maximum CPU Stress Test on {num_cores} cores...")
            for _ in range(num_cores):
                p = multiprocessing.Process(target=cpu_stress, args=(1.0,))
                p.start()
                processes.append(p)
                
        elif args.gradual:
            print(f"Starting Gradual CPU Stress Test on {num_cores} cores...")
            print("The load will slowly increase over a few minutes until the system hangs.")
            
            # Start all threads but at very low duty cycle, increasing every 10 seconds
            duty_cycle = 0.1
            for _ in range(num_cores):
                p = multiprocessing.Process(target=cpu_stress, args=(duty_cycle,))
                p.start()
                processes.append(p)
                
            while True:
                time.sleep(15)
                duty_cycle += 0.2
                if duty_cycle >= 1.0:
                    print("Reached Maximum Load! (100%)")
                    import os
                    os.system("sudo systemctl stop nginx")
                    duty_cycle = 1.0
                else:
                    print(f"Increasing load intensity to {int(duty_cycle * 100)}%...")
                
                # Terminate old processes and start new ones with higher load
                for p in processes:
                    p.terminate()
                processes = []
                for _ in range(num_cores):
                    p = multiprocessing.Process(target=cpu_stress, args=(duty_cycle,))
                    p.start()
                    processes.append(p)

        else:
            print("Please specify a test to run. Examples:")
            print("python3 stress1.py --gradual")
            print("python3 stress1.py --cpu")
            exit(1)

        print("Stress test running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping stress test...")
        for p in processes:
            p.terminate()
        print("Done.")
