from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from common.core.config import settings
from fastapi import FastAPI

def create_resource():

    return Resource(attributes={
        "service.name": settings.service_name,
        "service.version": settings.service_version,
        "service.environment": settings.environment,
    })

def setup_tracing(app: FastAPI):

    resource = create_resource()
    trace_provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace_provider.add_span_processor(span_processor)

    trace.set_tracer_provider(trace_provider)

    set_global_textmap(CompositePropagator(propagators=[
        TraceContextTextMapPropagator(),
        B3MultiFormat(),
    ]))

    RequestsInstrumentor().instrument()    
    FastAPIInstrumentor.instrument_app(app)

