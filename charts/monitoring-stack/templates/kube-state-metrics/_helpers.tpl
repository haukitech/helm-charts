{{- define "monitoring-stack.kube-state-metrics.name" -}}
{{- include "kube-state-metrics.name" ( get .Subcharts "kube-state-metrics" ) }}
{{- end }}

{{- define "monitoring-stack.kube-state-metrics.fullname" -}}
{{- include "kube-state-metrics.fullname" ( get .Subcharts "kube-state-metrics" ) }}
{{- end }}

{{- define "monitoring-stack.kube-state-metrics.labels" -}}
app.kubernetes.io/name: {{ include "monitoring-stack.kube-state-metrics.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{ include "monitoring-stack.labels" . }}
{{- end }}
