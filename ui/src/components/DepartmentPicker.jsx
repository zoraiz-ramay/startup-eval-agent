import React from "react";
import { IxSelect, IxSelectItem } from "@siemens/ix-react";

/* The one department selector: search, the profile's department switch and the Database grid
   all use it, so the list, its order and its labels cannot drift apart between screens.

   `allowAll` adds an "All departments" entry for filtering; a search never offers it, because
   every evaluation is for exactly one department. */
export default function DepartmentPicker({ departments, value, onChange, disabled, allowAll = false,
  label = "Department", placeholder = "Choose a department" }) {
  return (
    <IxSelect label={label} value={value || (allowAll ? "__all" : "")} disabled={disabled}
      placeholder={placeholder} aria-label={label} required={!allowAll}
      onValueChange={(e) => onChange(e.detail === "__all" ? "" : e.detail)}>
      {allowAll && <IxSelectItem value="__all" label="All departments" />}
      {departments.map((d) => <IxSelectItem key={d.id} value={d.id} label={d.demo ? `${d.label} (example needs)` : d.label} />)}
    </IxSelect>
  );
}
