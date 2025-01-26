{{- define "monitoring-stack.node-exporter.name" -}}
{{- include "prometheus-node-exporter.name" ( get .Subcharts "node-exporter" ) }}
{{- end }}

{{- define "monitoring-stack.node-exporter.fullname" -}}
{{- include "prometheus-node-exporter.fullname" ( get .Subcharts "node-exporter" ) }}
{{- end }}

{{- define "monitoring-stack.node-exporter.labels" -}}
app.kubernetes.io/name: {{ include "monitoring-stack.node-exporter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{ include "monitoring-stack.labels" . }}
{{- end }}
