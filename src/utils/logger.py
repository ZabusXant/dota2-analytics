import logging

root_logger = logging.getLogger("dota_data_logger")

if not root_logger.handlers:
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger.addHandler(stream_handler)
