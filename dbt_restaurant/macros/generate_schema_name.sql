{#
  Use the layer name as the schema (bronze / silver / gold) instead of dbt's
  default "<target>_<schema>", so reports can read gold.mart_* directly.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
