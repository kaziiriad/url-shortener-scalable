import logging
import sys

from services_python.common.core.config import settings
from services_python.common.core.tracing import create_resource
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

_logger_initialized = False  

def initialize_logger():
    global _logger_initialized
    if _logger_initialized:
        return logging.getLogger(__name__)
    _logger_initialized = True

    resource = create_resource()
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    otlp_exporter = OTLPLogExporter(endpoint=settings.otlp_endpoint, insecure=True)
    log_processor = BatchLogRecordProcessor(otlp_exporter)
    logger_provider.add_log_record_processor(log_processor)

    # Add console handler for immediate debugging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)

    logging.getLogger().addHandler(LoggingHandler())

    logger = logging.getLogger(__name__)
    logger.info("Logger initialized with console output")

    return logger


