{{- define "monitoring-stack.kubernetes-control-plane.name" -}}
kubernetes-control-plane
{{- end }}

{{- define "monitoring-stack.kubernetes-control-plane.fullname" -}}
kubernetes-control-plane
{{- end }}

{{- define "monitoring-stack.kubernetes-control-plane.labels" -}}
app.kubernetes.io/name: {{ include "monitoring-stack.kubernetes-control-plane.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{ include "monitoring-stack.labels" . }}
{{- end }}

{{- define "monitoring-stack.kube-controller-manager.name" -}}
kube-controller-manager
{{- end }}
