import pprint
from datetime import datetime


def log_request_data(request):
    """
    Prints a formatted, descriptive log of a GET or POST request's data.
    """
    method = request.method
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine which data to log based on the request method
    if method == "POST":
        data = dict(request.POST.lists())
        data_type = "POST"
    elif method == "GET":
        data = dict(request.GET.lists())
        data_type = "GET"
    else:
        # Handle other methods if needed
        return

    # Create a descriptive header
    header = f"--- {data_type} Request Data at {timestamp} ---"
    footer = "-" * len(header)

    # Print the formatted output to the console
    print(header)
    if data:
        pprint.pprint(data, indent=4)
    else:
        print("    No data found.")
    print(footer)
