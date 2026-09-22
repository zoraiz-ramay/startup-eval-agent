export function sameDepartment(saved, current) {
  return Boolean(saved && current && saved.label === current.label &&
    JSON.stringify(saved.interests) === JSON.stringify(current.interests));
}
export function departmentScore(run, department) {
  const saved = run.department_assessments?.[department?.id];
  return saved?.status === "assessed" && sameDepartment(saved.department, department) && typeof saved.score === "number" ? saved.score : null;
}
