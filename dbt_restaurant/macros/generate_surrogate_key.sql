{% macro generate_surrogate_key(field) %}
    MD5(CAST({{ field }} AS VARCHAR))
{% endmacro %}
