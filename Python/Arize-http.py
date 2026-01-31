from arize.otel import register, Transport
from opentelemetry import trace
from opentelemetry.trace import SpanKind

# Register Arize OTEL tracer provider
tracer_provider = register(
    endpoint="https://otlp.eu-west-1a.arize.com/v1/traces",
    space_id="U3BhY2U6NTE1OmZaUVc=",
    api_key="ak-e67a51ed-c916-4165-b425-24d1eab9e4e5-V2RIkfvg6NLxnurC_tjrfm2Z_DLAooUt",
    project_name="dat-dev-2",
    transport=Transport.HTTP,
)

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span(
    "dummy-span",
    kind=SpanKind.INTERNAL
) as span:
    span.set_attribute("test.attribute", "demo")
    span.add_event("This is a dummy event.")
    print("Inside dummy span!")

print("Script executed successfully")