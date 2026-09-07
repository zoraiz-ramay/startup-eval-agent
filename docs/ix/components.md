# iX React Components (ix-react 5.1.1 / ix 5.1.1)

Extracted from `@siemens/ix-react/dist/types/components/components.d.ts` (React export → web-component tag mapping) cross-referenced with `@siemens/ix/dist/types/components.d.ts` (the `Components` namespace, which declares each tag's props). Total components: **104**.

Each component below is importable as `import { <Name> } from '@siemens/ix-react'` and renders the web component `<tag>`. Props are listed as declared in the .d.ts — `?` means optional, `= value` is the `@default` from JSDoc where present. This mirrors DOM attribute/property names (some are camelCase properties without a matching HTML attribute; check the source for details on components you plan to use heavily).

## Buttons & Actions (7)

### `IxButton` (`<ix-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `alignment` | `'center' \| 'start'` | `'center'` |  |  |
| `disabled` | `boolean` | `false` |  | Disable the button |
| `form?` | `string` |  | 3.1.0 | Provide a form element ID to automatically submit the from if the button is pressed. Only works in combination with type="submit". |
| `href?` | `string` |  | 4.0.0 | URL for the button link. When provided, the button will render as an anchor tag. |
| `icon?` | `string` |  |  | Icon name |
| `iconRight?` | `string` |  | 4.0.0 | Icon name for the right side of the button |
| `iconSize` | `'12' \| '16' \| '24'` | `'24'` |  |  |
| `loading` | `boolean` | `false` |  | Loading button |
| `rel?` | `string` |  | 4.0.0 | Specifies the relationship between the current document and the linked document when href is provided. |
| `target?` | `AnchorTarget` | `'_self'` | 4.0.0 | Specifies where to open the linked document when href is provided. |
| `type` | `'button' \| 'submit'` | `'button'` |  | Type of the button |
| `variant` | `ButtonVariant` | `'primary'` |  | Button variant |

### `IxDropdownButton` (`<ix-dropdown-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelDropdownButton?` | `string` |  | 3.2.0 | ARIA label for the dropdown button Will be set as aria-label on the nested HTML button element |
| `closeBehavior` | `'inside' \| 'outside' \| 'both' \| boolean` | `'both'` |  | Controls if the dropdown will be closed in response to a click event depending on the position of the event relative to the dropdown. |
| `disabled` | `boolean` | `false` |  | Disable button |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `focusCheckedItem` | `boolean` | `false` | 5.0.0 | If true, the dropdown will try to focus checked items first when opened via keyboard, otherwise it will always focus the first focusable item. |
| `getDropdownReference` | `() => Promise<HTMLIxDropdownElement>` |  |  |  |
| `icon?` | `string` |  |  | Button icon |
| `label?` | `string \| null` |  |  | Set label |
| `placement?` | `AlignedPlacement` |  |  | Placement of the dropdown |
| `suppressAriaActiveDescendant` | `boolean` | `false` |  | Suppress the use of the aria-activedescendant attribute and related focus proxy functionality. |
| `variant` | `DropdownButtonVariant` | `'primary'` |  | Button variant |

### `IxIconButton` (`<ix-icon-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disabled` | `boolean` | `false` |  | Disabled |
| `icon?` | `string` |  |  | Icon name |
| `iconColor?` | `string` |  |  | Color of icon in button |
| `loading` | `boolean` | `false` |  | Loading button |
| `oval` | `boolean` | `false` |  | Button in oval shape |
| `size` | `'24' \| '16' \| '12'` | `'24'` |  | Size of icon in button |
| `type` | `'button' \| 'submit'` | `'button'` |  | Type of the button |
| `variant` | `IconButtonVariant` | `'subtle-primary'` |  | Variant of button |

### `IxIconToggleButton` (`<ix-icon-toggle-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disabled` | `boolean` | `false` |  | Disable the button |
| `ghost` | `boolean` | `false` |  | Button with no background or outline |
| `icon?` | `string` |  |  | Icon name |
| `loading` | `boolean` | `false` |  | Loading button |
| `outline` | `boolean` | `false` |  | Outline button |
| `oval` | `boolean` | `false` | 3.1.0 | Button in oval shape |
| `pressed` | `boolean` | `false` |  | Show button as pressed |
| `size` | `'24' \| '16' \| '12'` | `'24'` |  | Size of icon in button |
| `variant` | `ButtonVariant1` | `'subtle-primary'` |  | Button variant. |

### `IxLinkButton` (`<ix-link-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disabled` | `boolean` | `false` |  | Disable the link button |
| `target` | `'_self' \| '_blank' \| '_parent' \| '_top'` | `'_self'` |  | Specifies where to open the link https://www.w3schools.com/html/html_links.asp |
| `url?` | `string` |  |  | Url for the link button |

### `IxSplitButton` (`<ix-split-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelButton?` | `string` |  | 3.2.0 | ARIA label for the button (use if no label and icon button) |
| `ariaLabelSplitIconButton?` | `string` |  | 3.2.0 | ARIA label for the split icon button |
| `closeBehavior` | `CloseBehavior` | `'both'` |  | Controls if the dropdown will be closed in response to a click event depending on the position of the event relative to the dropdown. |
| `disableButton` | `boolean` | `false` | 4.1.0 | Disables only the main button while keeping the dropdown trigger enabled |
| `disableDropdownButton` | `boolean` | `false` | 4.1.0 | Disables only the dropdown trigger while keeping the main button enabled |
| `disabled` | `boolean` | `false` |  | Disabled |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `icon?` | `string` |  |  | Button icon |
| `label?` | `string` |  |  | Button label |
| `splitIcon?` | `string` |  |  | Icon of the button on the right |
| `variant` | `SplitButtonVariant` | `'primary'` |  | Color variant of button |

### `IxToggleButton` (`<ix-toggle-button>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disabled` | `boolean` | `false` |  | Disable the button |
| `icon?` | `string` |  |  | Icon name |
| `iconRight?` | `string` |  | 4.0.0 | Icon name for the right side of the button |
| `loading` | `boolean` | `false` |  | Loading button |
| `pressed` | `boolean` | `false` |  | Show button as pressed |
| `variant` | `ToggleButtonVariant` | `'subtle-primary'` |  | Button variant. |

## Forms & Inputs (23)

### `IxCheckbox` (`<ix-checkbox>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `checked` | `boolean` | `false` |  | Checked state of the checkbox component |
| `disabled` | `boolean` | `false` |  | Disabled state of the checkbox component |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `indeterminate` | `boolean` | `false` |  | Indeterminate state of the checkbox component |
| `isTouched` | `() => Promise<boolean>` |  |  |  |
| `label?` | `string` |  |  | Label for the checkbox component |
| `name?` | `string` |  |  | Name of the checkbox component |
| `required` | `boolean` | `false` |  | Required state of the checkbox component. If true, checkbox needs to be checked to be valid |
| `value` | `string` | `'on'` |  | Value of the checkbox component |

### `IxCheckboxGroup` (`<ix-checkbox-group>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `direction` | `'row' \| 'column'` | `'column'` |  | Alignment of the checkboxes in the group |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | Optional helper text displayed below the checkbox group |
| `infoText?` | `string` |  |  | Info text for the checkbox group |
| `invalidText?` | `string` |  |  | Error text for the checkbox group |
| `isTouched` | `() => Promise<boolean>` |  |  |  |
| `label?` | `string` |  |  | Label for the checkbox group |
| `required` | `boolean` | `false` |  |  |
| `showTextAsTooltip` | `boolean` | `false` |  | Show helper, info, warning, error and valid text as tooltip |
| `validText?` | `string` |  |  | Valid text for the checkbox group |
| `warningText?` | `string` |  |  | Warning text for the checkbox group |

### `IxCustomField` (`<ix-custom-field>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `helperText?` | `string` |  |  | Show text below the field component which show additional information |
| `infoText?` | `string` |  |  | Info text for the field component |
| `invalidText?` | `string` |  |  | Error text for the field component |
| `label?` | `string` |  |  | Label for the field component |
| `required` | `boolean` | `false` |  | A value is required or must be checked for the form to be submittable |
| `showTextAsTooltip?` | `boolean` |  |  | Show helper, info, warning, error and valid text as tooltip |
| `validText?` | `string` |  |  | Valid text for the field component |
| `warningText?` | `string` |  |  | Warning text for the field component |

### `IxDateDropdown` (`<ix-date-dropdown>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `dateRangeId` | `string` | `'custom'` |  | Used to set the initial select date range as well as the button name, if not set or no according date range label is found, nothing will be selected |
| `dateRangeOptions` | `DateDropdownOption[]` | `[]` |  | An array of predefined date range options for the date picker. Each option is an object with a label describing the range and a function that returns the start and end dates of the range as a DateRangeOption object. Example format: { id: 'some unique id', label: 'Name of the range', from: undefined, to: '2023/03/29' }, // ... other predefined date range options ... |
| `disabled` | `boolean` | `false` |  | Disable the button that opens the dropdown containing the date picker. |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `format` | `string` | `'yyyy/LL/dd'` |  | Date format string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `from` | `string` | `''` |  | Picker date. If the picker is in range mode this property is the start date. If set to `null` no default start date will be pre-selected. Format is based on `format` |
| `getDateRange` | `() => Promise<DateRangeChangeEvent>` |  |  | Retrieves the currently selected date range from the component. This method returns the selected date range as a `DateChangeEvent` object. |
| `i18nDone` | `string` | `'Done'` |  | Text for the done button. Will be used for translation. |
| `i18nNoRange` | `string` | `'No` |  | Text for the done button. Will be used for translation.  range set' |
| `loading` | `boolean` | `false` |  | Loading button |
| `locale?` | `string` |  |  | Locale identifier (e.g. 'en' or 'de'). |
| `maxDate` | `string` | `''` |  | The latest date that can be selected by the date picker. If not set there will be no restriction. |
| `minDate` | `string` | `''` |  | The earliest date that can be selected by the date picker. If not set there will be no restriction. |
| `showWeekNumbers` | `boolean` | `false` | 3.0.0 | Shows week numbers displayed on the left side of the date picker |
| `singleSelection` | `boolean` | `false` |  | If true disables date range selection (from/to). |
| `to` | `string` | `''` |  | Picker date. If the picker is in range mode this property is the end date. If the picker is not in range mode leave this value `null` Format is based on `format` |
| `today` | `string` | `DateTime.now().toISO()` |  |  |
| `variant` | `ButtonVariant1` | `'primary'` |  | Button variant |
| `weekStartIndex` | `number` | `0` |  | The index of which day to start the week on, based on the Locale#weekdays array. E.g. if the locale is en-us, weekStartIndex = 1 results in starting the week on monday. |

### `IxDateInput` (`<ix-date-input>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCalendarButton?` | `string` | `'Open` | 3.2.0 | ARIA label for the calendar icon button. Will be set as aria-label on the nested HTML button element.   calendar' |
| `ariaLabelNextMonthButton?` | `string` | `'Next` |  | ARIA label for the next month icon button. Will be set as aria-label on the nested HTML button element.  month' |
| `ariaLabelPreviousMonthButton?` | `string` | `'Previous` |  | ARIA label for the previous month icon button. Will be set as aria-label on the nested HTML button element.  month' |
| `disabled` | `boolean` | `false` |  | Disabled attribute. |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `focusInput` | `() => Promise<void>` |  |  | Focuses the input field |
| `format` | `string` | `'yyyy/LL/dd'` |  | Date format string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `getNativeInputElement` | `() => Promise<HTMLInputElement>` |  |  | Get the native input element |
| `getValidityState` | `() => Promise<ValidityState>` |  |  |  |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | Helper text below the input field. |
| `i18nErrorDateUnparsable` | `string` | `'Date` |  | I18n string for the error message when the date is not parsable.  is not valid' |
| `infoText?` | `string` |  |  | Info text below the input field. |
| `invalidText?` | `string` |  |  | Error text below the input field. |
| `isTouched` | `() => Promise<boolean>` |  |  | Returns whether the text field has been touched. |
| `label?` | `string` |  |  | Label of the input field. |
| `locale?` | `string` |  |  | Locale identifier (e.g. 'en' or 'de'). The locale is used to translate the labels for weekdays and months. It also determines the default order of weekdays based on the locale's conventions. When the locale changes, the weekday labels are rotated according to the `weekStartIndex`. It does not affect the values returned by methods and events. |
| `maxDate` | `string` | `''` |  | The latest date that can be selected by the date input/picker. If not set there will be no restriction. |
| `minDate` | `string` | `''` |  | The earliest date that can be selected by the date input/picker. If not set there will be no restriction. |
| `name?` | `string` |  |  | Name of the input element. |
| `openPicker` | `() => Promise<void>` |  |  |  |
| `placeholder?` | `string` |  |  | Placeholder of the input element. |
| `readonly` | `boolean` | `false` |  | Readonly attribute. |
| `required?` | `boolean` |  |  | Required attribute. |
| `showTextAsTooltip?` | `boolean` |  |  | Show text as tooltip. |
| `showWeekNumbers` | `boolean` | `false` | 3.0.0 | Shows week numbers displayed on the left side of the date picker. |
| `suppressSubmitOnEnter` | `boolean` | `false` |  | If false, pressing Enter will submit the form (if inside a form). Set to true to suppress submit on Enter. |
| `textAlignment` | `'start' \| 'end'` | `'start'` |  | Text alignment within the date input. 'start' aligns the text to the start of the input, 'end' aligns the text to the end of the input. |
| `validText?` | `string` |  |  | Valid text below the input field. |
| `value?` | `string` | `''` |  | Value of the input element. |
| `warningText?` | `string` |  |  | Warning text below the input field. |
| `weekStartIndex` | `number` | `0` |  | The index of which day to start the week on, based on the Locale#weekdays array. E.g. if the locale is en-us, weekStartIndex = 1 results in starting the week on Monday. |

### `IxDatePicker` (`<ix-date-picker>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelMonthSelection?` | `string` | `'Select` | 5.0.0 | ARIA label for the next month icon button Will be set as aria-label on the nested HTML button element   month' |
| `ariaLabelNextMonthButton?` | `string` | `'Change` |  | ARIA label for the next month icon button. Will be set as aria-label on the nested HTML button element.  calendar view to next month' |
| `ariaLabelPreviousMonthButton?` | `string` | `'Change` |  | ARIA label for the previous month icon button. Will be set as aria-label on the nested HTML button element.  calendar view to previous month' |
| `ariaLabelYearSelection?` | `string` | `'Select` | 5.0.0 | ARIA label for the next month icon button Will be set as aria-label on the nested HTML button element   year' |
| `corners` | `DateTimeCardCorners` | `'rounded'` |  | Corner style. |
| `embedded` | `boolean` | `false` |  |  |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `focusActiveDay` | `() => Promise<void>` |  |  |  |
| `focusFirstDayOfCurrentWeek` | `() => Promise<void>` |  |  |  |
| `focusLastDayOfCurrentWeek` | `() => Promise<void>` |  |  |  |
| `format` | `string` | `'yyyy/LL/dd'` |  | Date format string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `from` | `string \| undefined` |  |  | The selected starting date. If the date picker is not in range mode, this is the selected date. Format has to match the `format` property. |
| `getCurrentDate` | `() => Promise<DateChangeEvent>` |  |  | Get the currently selected date or range. The object returned contains `from` and `to` properties. The property strings are formatted according to the `format` property and not affected by the `locale` property. The locale applied is always `en-US`. |
| `i18nDone` | `string` | `'Done'` |  | Text of the date select button. |
| `isCalendarDayFocused` | `() => Promise<boolean>` |  |  |  |
| `locale?` | `string` |  |  | Locale identifier (e.g. 'en' or 'de'). The locale is used to translate the labels for weekdays and months. It also determines the default order of weekdays based on the locale's conventions. When the locale changes, the weekday labels are rotated according to the `weekStartIndex`. It does not affect the values returned by methods and events. |
| `maxDate` | `string` | `''` |  | The latest date that can be selected by the date picker. If not set there will be no restriction. |
| `minDate` | `string` | `''` |  | The earliest date that can be selected by the date picker. If not set there will be no restriction. |
| `navigateCalendar` | `(direction: -1 \| 1, byYear: boolean) => Promise<void>` |  |  |  |
| `showWeekNumbers` | `boolean` | `false` | 3.0.0 | Shows week numbers displayed on the left side of the date picker. |
| `singleSelection` | `boolean` | `false` |  | If true, disables date range selection (from/to). |
| `to` | `string \| undefined` |  |  | The selected end date. If the date picker is not in range mode, this property has no impact. Format has to match the `format` property. |
| `today` | `string` | `DateTime.now().toISO()` |  |  |
| `updateSelectedYearMonth` | `(date: DateTime) => Promise<void>` |  |  |  |
| `weekStartIndex` | `number` | `0` |  | The index of which day to start the week on, based on the Locale#weekdays array. E.g. if the locale is en-us, weekStartIndex = 1 results in starting the week on Monday. |

### `IxDatetimeInput` (`<ix-datetime-input>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCalendarButton?` | `string` | `'Toggle` |  | ARIA label for the calendar icon button Will be set as aria-label on the nested HTML button element  calendar' |
| `ariaLabelNextMonthButton?` | `string` | `'Next` |  | ARIA label for next month navigation button  month' |
| `ariaLabelPreviousMonthButton?` | `string` | `'Previous` |  | ARIA label for previous month navigation button  month' |
| `disabled` | `boolean` | `false` |  | Whether the input is disabled |
| `enableTopLayer` | `boolean` | `false` |  | Enable Popover API rendering for dropdown. |
| `focusInput` | `() => Promise<void>` |  |  | Focus the native input element |
| `format` | `string` | `'yyyy/LL/dd` |  | Luxon date and time format for display (e.g., 'yyyy/LL/dd HH:mm:ss' → "2026/01/20 13:07:04"). See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens.  HH:mm:ss' |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  | Returns the associated HTML form element. |
| `getNativeInputElement` | `() => Promise<HTMLInputElement>` |  |  | Get the native input element |
| `getValidityState` | `() => Promise<ValidityState>` |  |  | Returns the validity state of the input. |
| `hasValidValue` | `() => Promise<boolean>` |  |  | Returns whether the input has a value. |
| `helperText?` | `string` |  |  | Helper text displayed below the input |
| `i18nDone` | `string` | `'Confirm'` |  | Text for confirm button in picker (prop name matches datetime-picker) |
| `i18nErrorDateTimeUnparsable` | `string` | `'Date` |  | Error message when datetime cannot be parsed  time is not valid' |
| `i18nTime` | `string` | `'Time'` |  | Header text for time picker section |
| `infoText?` | `string` |  |  | Informational message |
| `invalidText?` | `string` |  |  | Validation message for invalid state |
| `isTouched` | `() => Promise<boolean>` |  |  | Returns whether the input field has been touched. |
| `label?` | `string` |  |  | Label text displayed above the input |
| `locale?` | `string` |  |  | Locale for date/time formatting (e.g., 'en-US', 'de-DE') |
| `maxDate?` | `string` |  |  | Maximum allowed date (matching format or date-only, e.g., "2026/12/31") |
| `maxTime?` | `string` |  | 5.0.0 | Latest selectable time (tokens matching the time portion of `format`). Invalid non-empty values are ignored. |
| `minDate?` | `string` |  |  | Minimum allowed date (matching format or date-only, e.g., "2026/01/20") |
| `minTime?` | `string` |  | 5.0.0 | Earliest selectable time (tokens matching the time portion of `format`). Invalid non-empty values are ignored. |
| `name?` | `string` |  |  | Name of the form control for form submission |
| `openPicker` | `() => Promise<void>` |  |  |  |
| `placeholder?` | `string` |  |  | Placeholder text when input is empty |
| `readonly` | `boolean` | `false` |  | Whether the input is read-only (calendar icon hidden) |
| `required` | `boolean` | `false` |  | Whether the field is required |
| `showTextAsTooltip` | `boolean` | `false` |  | Show helper text as tooltip instead of below input |
| `showWeekNumbers` | `boolean` | `false` |  | Show week numbers in date picker |
| `suppressSubmitOnEnter` | `boolean` | `false` |  | Prevent form submission when Enter is pressed |
| `textAlignment` | `'start' \| 'end'` | `'start'` |  | Text alignment within the input field |
| `validText?` | `string` |  |  | Success/valid message |
| `value?` | `string` | `''` |  | Value in display format (e.g., "2026/01/21 13:07:04" for default format) |
| `warningText?` | `string` |  |  | Warning message |
| `weekStartIndex` | `number` | `0` |  | First day of week (0=Sunday, 1=Monday, etc.) |

### `IxDatetimePicker` (`<ix-datetime-picker>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelNextMonthButton?` | `string` | `'Next` |  | ARIA label for the next month icon button. Will be set as aria-label on the nested HTML button element.  month' |
| `ariaLabelPreviousMonthButton?` | `string` | `'Previous` |  | ARIA label for the previous month icon button. Will be set as aria-label on the nested HTML button element.  month' |
| `dateFormat` | `string` | `'yyyy/LL/dd'` |  | Date format string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `embedded` | `boolean` | `false` |  |  |
| `from?` | `string` |  |  | The selected starting date. If the picker is not in range mode, this is the selected date. Format has to match the `dateFormat` property. |
| `getDatepickerElement` | `() => Promise<HTMLIxDatePickerElement \| undefined>` |  |  |  |
| `getTimepickerElement` | `() => Promise<HTMLIxTimePickerElement \| undefined>` |  |  |  |
| `i18nDone` | `string` | `'Done'` |  | Text of the date select button. |
| `i18nTime` | `string` | `'Time'` | 3.0.0 | Top label of the time picker. |
| `locale?` | `string` |  |  | Locale identifier (e.g. 'en' or 'de'). See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `maxDate?` | `string` |  |  | The latest date that can be selected. If not set there will be no restriction. |
| `maxTime?` | `string` |  | 5.0.0 | Latest selectable time (`timeFormat` tokens). Invalid non-empty values are ignored. |
| `minDate?` | `string` |  |  | The earliest date that can be selected. If not set there will be no restriction. |
| `minTime?` | `string` |  | 5.0.0 | Earliest selectable time (`timeFormat` tokens). Invalid non-empty values are ignored. |
| `showTimeReference` | `boolean` | `false` |  | Show AM/PM time reference control. |
| `showWeekNumbers` | `boolean` | `false` | 3.0.0 | Shows week numbers displayed on the left side of the date picker. |
| `singleSelection` | `boolean` | `false` |  | If true, disables date range selection (from/to). |
| `time?` | `string` |  |  | Selected time value for the embedded time picker. Format has to match the `timeFormat` property. |
| `timeFormat` | `string` | `'HH:mm:ss'` |  | Time format string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `timeReference?` | `'AM' \| 'PM'` |  |  | Time reference (AM or PM). |
| `to?` | `string` |  |  | The selected end date. If the picker is not in range mode, this property has no impact. Format has to match the `dateFormat` property. |
| `weekStartIndex` | `number` | `0` |  | The index of which day to start the week on, based on the Locale#weekdays array. E.g. if the locale is en-us, weekStartIndex = 1 results in starting the week on Monday. |

### `IxExpandingSearch` (`<ix-expanding-search>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelClearIconButton?` | `string` | `'Clear` | 3.2.0 | ARIA label for the clear icon button Will be set as aria-label on the nested HTML button element   search' |
| `ariaLabelSearchIconButton?` | `string` |  | 3.2.0 | ARIA label for the search icon button Will be set as aria-label on the nested HTML button element |
| `ariaLabelSearchInput?` | `string` | `'Search` | 3.2.0 | ARIA label for the search input Will be set as aria-label on the nested HTML input element   input' |
| `fullWidth` | `boolean` | `false` |  | If true the search field will fill all available horizontal space of it's parent container when expanded. |
| `icon?` | `string` |  |  | Search icon |
| `placeholder` | `string` | `'Enter` |  | Placeholder text  text here' |
| `value` | `string` | `''` |  | Default value |
| `variant` | `ButtonVariant1` | `'tertiary'` |  | button variant |

### `IxFieldLabel` (`<ix-field-label>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `controlRef?` | `\| MakeRef<HTMLElement>
    \| MakeRef<HTMLInputElement>
    \| MakeRef<HTMLTextAreaElement>` |  |  |  |
| `htmlFor?` | `string` |  |  | The id of the form element that the label is associated with |
| `isInvalid` | `boolean` | `false` |  |  |
| `required?` | `boolean` |  |  | A value is required or must be checked for the form to be submittable |

### `IxHelperText` (`<ix-helper-text>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `helperText?` | `string` |  |  | Show text below the field component |
| `htmlFor?` | `string` |  |  | The id of the form element that the label is associated with |
| `infoText?` | `string` |  |  | Info text for the field component |
| `invalidText?` | `string` |  |  | Error text for the field component |
| `validText?` | `string` |  |  | Valid text for the field component |
| `warningText?` | `string` |  |  | Warning text for the field component |

### `IxInput` (`<ix-input>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `allowedCharactersPattern?` | `string` |  |  | The allowed characters pattern for the text field. |
| `disabled` | `boolean` | `false` |  | Specifies whether the text field is disabled. |
| `focusInput` | `() => Promise<void>` |  |  | Focuses the input field |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `getNativeInputElement` | `() => Promise<HTMLInputElement>` |  |  | Returns the native input element used in the text field. |
| `getValidityState` | `() => Promise<ValidityState>` |  |  | Returns the validity state of the input field. |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | The helper text for the text field. |
| `infoText?` | `string` |  |  | The info text for the text field. |
| `invalidText?` | `string` |  |  | The error text for the text field. |
| `isTouched` | `() => Promise<boolean>` |  |  | Returns whether the text field has been touched. |
| `label?` | `string` |  |  | The label for the text field. |
| `maxLength?` | `number` |  |  | The maximum length of the text field. |
| `minLength?` | `number` |  |  | The minimum length of the text field. |
| `name?` | `string` |  |  | The name of the text field. |
| `pattern?` | `string` |  |  | The pattern for the text field. |
| `placeholder?` | `string` |  |  | The placeholder text for the text field. |
| `readonly` | `boolean` | `false` |  | Specifies whether the text field is readonly. |
| `required` | `boolean` | `false` |  | Specifies whether the text field is required. |
| `showTextAsTooltip?` | `boolean` |  |  | Specifies whether to show the text as a tooltip. |
| `suppressSubmitOnEnter` | `boolean` | `false` |  | If false, pressing Enter will submit the form (if inside a form). Set to true to suppress submit on Enter. |
| `textAlignment` | `'start' \| 'end'` | `'start'` |  | Text alignment within the input. 'start' aligns the text to the start of the input, 'end' aligns the text to the end of the input. |
| `type` | `'text' \| 'email' \| 'password' \| 'tel' \| 'url'` | `'text'` |  | The type of the text field. Possible values are 'text', 'email', or 'password'. |
| `validText?` | `string` |  |  | The valid text for the text field. |
| `value` | `string` | `''` |  | The value of the text field. |
| `warningText?` | `string` |  |  | The warning text for the text field. |

### `IxNumberInput` (`<ix-number-input>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `allowEmptyValueChange` | `boolean` | `false` | 4.1.0 | If true, the valueChange event will return null instead of 0 for an empty input state. This property will be removed in 5.0.0 and this behaviour will be default. |
| `allowedCharactersPattern?` | `string` |  |  | The allowed characters pattern for the input field |
| `disabled` | `boolean` | `false` |  | Disables the input field |
| `focusInput` | `() => Promise<void>` |  |  | Focuses the input field |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `getNativeInputElement` | `() => Promise<HTMLInputElement>` |  |  | Returns the native input element used under the hood |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | The helper text for the input field |
| `infoText?` | `string` |  |  | The info text for the input field |
| `invalidText?` | `string` |  |  | The error text for the input field |
| `isTouched` | `() => Promise<boolean>` |  |  | Returns true if the input field has been touched |
| `label?` | `string` |  |  | The label for the input field |
| `max?` | `string \| number` |  |  | The maximum value for the input field |
| `min?` | `string \| number` |  |  | The minimum value for the input field |
| `name?` | `string` |  |  | name of the input element |
| `pattern?` | `string` |  |  | The pattern for the input field |
| `placeholder?` | `string` |  |  | placeholder of the input element |
| `readonly` | `boolean` | `false` |  | Indicates if the field is read-only |
| `required` | `boolean` | `false` |  | Indicates if the field is required. When required, empty values (undefined) are not accepted. |
| `showStepperButtons?` | `boolean` |  |  | Indicates if the stepper buttons should be shown |
| `showTextAsTooltip?` | `boolean` |  |  | Indicates if the text should be shown as a tooltip |
| `step?` | `string \| number` | `1` |  | Step value to increment or decrement the input value. Default step value is 1. |
| `suppressSubmitOnEnter` | `boolean` | `false` |  | If false, pressing Enter will submit the form (if inside a form). Set to true to suppress submit on Enter. |
| `textAlignment` | `'start' \| 'end'` | `'end'` |  | Text alignment within the number input. 'start' aligns the text to the start of the input, 'end' aligns the text to the end of the input. |
| `validText?` | `string` |  |  | The valid text for the input field |
| `value?` | `number` | `0` |  | The value of the input field. Supports numeric values, scientific notation (1E6, 1E-6), or undefined for empty. |
| `warningText?` | `string` |  |  | The warning text for the input field |

### `IxRadio` (`<ix-radio>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `checked` | `boolean` | `false` |  | Checked state of the radio component |
| `disabled` | `boolean` | `false` |  | Disabled state of the radio component |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `label?` | `string` |  |  | Label for the radio component |
| `name?` | `string` |  |  | Name of the radio component |
| `required` | `boolean` | `false` | 3.0.0 | Requires the radio component and its group to be checked for the form to be submittable |
| `setCheckedState` | `(newChecked: boolean) => Promise<void>` |  |  |  |
| `value?` | `string` |  |  | Value of the radio component |

### `IxRadioGroup` (`<ix-radio-group>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `direction` | `'column' \| 'row'` | `'column'` |  | Alignment of the radio buttons in the group |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | Show text below the field component |
| `infoText?` | `string` |  |  | Info text for the field component |
| `invalidText?` | `string` |  |  | Error text for the field component |
| `isTouched` | `() => Promise<boolean>` |  |  |  |
| `label?` | `string` |  |  | Label for the field component |
| `required?` | `boolean` | `false` |  | Required state of the checkbox component |
| `setCheckedToNextItem` | `(currentRadio: HTMLIxRadioElement, forward?: boolean) => Promise<void>` |  |  |  |
| `showTextAsTooltip?` | `boolean` |  |  | Show helper, info, warning, error and valid text as tooltip |
| `validText?` | `string` |  |  | Valid text for the field component |
| `value?` | `string` |  |  | Value of the radiobutton group component |
| `warningText?` | `string` |  |  | Warning text for the field component |

### `IxSelect` (`<ix-select>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `allowClear` | `boolean` | `false` |  | Show clear button |
| `ariaLabelAddItem` | `string` | `'Add` | TODO: | ARIA label for the add item  Define  item' |
| `ariaLabelClearIconButton?` | `string` | `'Clear` | 3.2.0 | ARIA label for the clear icon button Will be set as aria-label on the nested HTML button element   selection' |
| `collapseMultipleSelection` | `boolean` | `false` |  | Show "all" chip when all items are selected in multiple mode |
| `disabled` | `boolean` | `false` |  | If true the select will be in disabled state |
| `dropdownMaxWidth?` | `string` |  |  | The maximum width of the dropdown element with value and unit (e.g. "200px" or "12.5rem"). By default the maximum width of the dropdown element is set to 100%. |
| `dropdownWidth?` | `string` |  |  | The width of the dropdown element with value and unit (e.g. "200px" or "12.5rem"). |
| `editable` | `boolean` | `false` |  | Select is extendable |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `focusInput` | `() => Promise<void>` |  |  | Focuses the input field |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `getNativeInputElement` | `() => Promise<HTMLInputElement>` |  |  | Returns the native input element used in the component. |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | Helper text for the select component |
| `hideListHeader` | `boolean` | `false` |  | Hide list header |
| `i18nAllSelected` | `string` | `'All'` |  | Chip label for all selected items in multiple mode. |
| `i18nMoreItems` | `string` | `'{count}` | 5.1.0 | Accessible label template for the overflow indicator chip shown in multiple mode when not all selected chips fit on a single row. The `{count}` placeholder is replaced with the number of hidden items (e.g. "3 more").   more' |
| `i18nNoMatches` | `string` | `'No` |  | Information inside of dropdown if no items where found with current filter text  matches' |
| `i18nPlaceholder` | `string` | `'Select` |  | Input field placeholder  an option' |
| `i18nPlaceholderEditable` | `string` | `'Type` |  | Input field placeholder for editable select  of select option' |
| `i18nRemoveSelectedItem` | `string` | `'Remove'` | 5.0.0 | Prefix for the accessible name of the close control on a selected chip in multiple mode. The chip label or value is appended (e.g. "Remove Item 1"). |
| `i18nSelectListHeader` | `string` | `'Select` |  | Select list header  an option' |
| `infoText?` | `string` |  |  | Info text for the select component |
| `invalidText?` | `string` |  |  | Error text for the select component |
| `isTouched` | `() => Promise<boolean>` |  |  | Check if the input field has been touched. |
| `label?` | `string` |  |  | Label for the select component |
| `mode` | `'single' \| 'multiple'` | `'single'` |  | Selection mode |
| `name?` | `string` |  |  | A string that represents the element's name attribute, containing a name that identifies the element when submitting the form. |
| `readonly` | `boolean` | `false` |  | If true the select will be in readonly mode |
| `required` | `boolean` | `false` |  | A Boolean attribute indicating that an option with a non-empty string value must be selected |
| `showTextAsTooltip?` | `boolean` |  |  | Show helper, error, info, warning text as tooltip |
| `validText?` | `string` |  |  | Valid text for the select component |
| `value` | `string \| string[]` | `''` |  | Current selected value. This corresponds to the value property of ix-select-items |
| `warningText?` | `string` |  |  | Warning text for the select component |

### `IxSelectItem` (`<ix-select-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disableAriaSelectHandling` | `boolean` | `false` |  | When `true`, do not map keyboard focus visibility to `aria-selected` on the host. Use when selection state must not mirror roving focus (e.g. `ix-select-item`). |
| `disabled` | `boolean` | `false` | 5.1.0 | Disable the item. A disabled item cannot be selected via mouse or keyboard and is excluded from the focusable items of the parent ix-select. |
| `getDropdownItemElement` | `() => Promise<HTMLIxDropdownItemElement>` |  |  |  |
| `hover` | `boolean` | `false` |  |  |
| `ixFocusVisible` | `boolean` | `false` |  |  |
| `label?` | `string` |  |  | Displayed name of the item |
| `selected` | `boolean` | `false` |  | Flag indicating whether the item is selected |
| `value` | `string` |  |  | The value of the item. Important: The select component uses string values to handle selection and will call toString() on this value. Therefor a string should be passed to value to prevent unexpected behavior. |

### `IxSlider` (`<ix-slider>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disabled` | `boolean` | `false` |  | Show control as disabled |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  | 4.3.0 | Show text below the field component |
| `infoText?` | `string` |  | 4.3.0 | Info text for the field component |
| `invalidText?` | `string` |  | 4.3.0 | Error text for the field component |
| `isTouched` | `() => Promise<boolean>` |  |  |  |
| `label?` | `string` |  | 4.3.0 | Label for the field component |
| `marker?` | `SliderMarker` |  |  | Define tick marker on the slider. Marker has to be within slider min/max |
| `max` | `number` | `100` |  | Maximum slider value |
| `min` | `number` | `0` |  | Minimum slider value |
| `showTextAsTooltip` | `boolean` | `false` | 4.3.0 | Show helper, info, warning, error and valid text as tooltip |
| `step` | `number` | `1` |  | Legal number intervals {@link https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/range#step} |
| `trace` | `boolean` | `false` |  | Show a trace line |
| `traceReference` | `number` | `0` |  | Define the start point of the trace line |
| `validText?` | `string` |  | 4.3.0 | Valid text for the field component |
| `value` | `number` | `0` |  | Current value of the slider |
| `warningText?` | `string` |  | 4.3.0 | Warning text for the field component |

### `IxTextarea` (`<ix-textarea>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `disabled` | `boolean` | `false` |  | Determines if the textarea field is disabled. |
| `focusInput` | `() => Promise<void>` |  |  | Focuses the input field |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `getNativeInputElement` | `() => Promise<HTMLTextAreaElement>` |  |  | Get the native textarea element. |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | The helper text for the textarea field. |
| `infoText?` | `string` |  |  | The info text for the textarea field. |
| `invalidText?` | `string` |  |  | The error text for the textarea field. |
| `isTouched` | `() => Promise<boolean>` |  |  | Check if the textarea field has been touched. |
| `label?` | `string` |  |  | The label for the textarea field. |
| `maxLength?` | `number` |  |  | The maximum length of the textarea field. |
| `minLength?` | `number` |  |  | The minimum length of the textarea field. |
| `name?` | `string` |  |  | The name of the textarea field. |
| `placeholder?` | `string` |  |  | The placeholder text for the textarea field. |
| `readonly` | `boolean` | `false` |  | Determines if the textarea field is readonly. |
| `required` | `boolean` | `false` |  | Determines if the textarea field is required. |
| `resizeBehavior` | `TextareaResizeBehavior` | `'both'` |  | Determines the resize behavior of the textarea field. Resizing can be enabled in one direction, both directions or completely disabled. |
| `showTextAsTooltip?` | `boolean` |  |  | Determines if the text should be displayed as a tooltip. |
| `textareaCols?` | `number` |  |  | The width of the textarea specified by number of characters. Will be overridden by `textareaWidth` prop if both are set. |
| `textareaHeight?` | `string` |  |  | The height of the textarea field (e.g. "52px"). Will take precedence over `textareaRows` prop if both are set. |
| `textareaRows?` | `number` |  |  | The height of the textarea specified by number of rows. Will be overridden by `textareaHeight` prop if both are set. |
| `textareaWidth?` | `string` |  |  | The width of the textarea field (e.g. "200px"). Will take precedence over `textareaCols` prop if both are set. |
| `validText?` | `string` |  |  | The valid text for the textarea field. |
| `value` | `string` | `''` |  | The value of the textarea field. |
| `warningText?` | `string` |  |  | The warning text for the textarea field. |

### `IxTimeInput` (`<ix-time-input>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelTimeToggleButton?` | `string` | `'Toggle` | 5.0.0 | ARIA label for the time picker toggle button Will be set as aria-label for the nested HTML button element   time picker' |
| `disabled` | `boolean` | `false` |  | Disabled attribute. |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `focusInput` | `() => Promise<void>` |  |  | Focuses the input field |
| `format` | `string` | `'TT'` |  | Format of time string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `getNativeInputElement` | `() => Promise<HTMLInputElement>` |  |  | Get the native input element |
| `getValidityState` | `() => Promise<ValidityState>` |  |  |  |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `helperText?` | `string` |  |  | Helper text below the input field. |
| `hideHeader` | `boolean` | `false` | 4.0.0 | Hides the header of the picker. |
| `hourInterval` | `number` | `1` |  | Interval for hour selection. |
| `i18nErrorTimeUnparsable` | `string` | `'Time` |  | I18n string for the error message when the time is not parsable.  is not valid' |
| `i18nHourColumnHeader` | `string` | `'hr'` |  | Text for the time picker hour column header. |
| `i18nMillisecondColumnHeader` | `string` | `'ms'` |  | Text for the time picker millisecond column header. |
| `i18nMinuteColumnHeader` | `string` | `'min'` |  | Text for the time picker minute column header. |
| `i18nSecondColumnHeader` | `string` | `'sec'` |  | Text for the time picker second column header. |
| `i18nSelectTime` | `string` | `'Confirm'` |  | Text of the time picker confirm button. |
| `i18nTime` | `string` | `'Time'` |  | Text for the time picker top label. |
| `infoText?` | `string` |  |  | Info text below the input field. |
| `invalidText?` | `string` |  |  | Error text below the input field. |
| `isTouched` | `() => Promise<boolean>` |  |  | Returns whether the text field has been touched. |
| `label?` | `string` |  |  | Label of the input field. |
| `maxTime?` | `string` |  | 5.0.0 | Latest selectable time (`format` tokens). Invalid non-empty values are ignored. |
| `millisecondInterval` | `number` | `100` |  | Interval for millisecond selection. |
| `minTime?` | `string` |  | 5.0.0 | Earliest selectable time (`format` tokens). Invalid non-empty values are ignored. |
| `minuteInterval` | `number` | `1` |  | Interval for minute selection. |
| `name?` | `string` |  |  | Name of the input element. |
| `openPicker` | `() => Promise<void>` |  |  |  |
| `placeholder?` | `string` |  |  | Placeholder of the input element. |
| `readonly` | `boolean` | `false` |  | Readonly attribute. |
| `required?` | `boolean` |  |  | Required attribute. |
| `secondInterval` | `number` | `1` |  | Interval for second selection. |
| `showTextAsTooltip?` | `boolean` |  |  | Show text as tooltip. |
| `suppressSubmitOnEnter` | `boolean` | `false` |  | If false, pressing Enter will submit the form (if inside a form). Set to true to suppress submit on Enter. |
| `textAlignment` | `'start' \| 'end'` | `'start'` |  | Text alignment within the time input. 'start' aligns the text to the start of the input, 'end' aligns the text to the end of the input. |
| `validText?` | `string` |  |  | Valid text below the input field. |
| `value` | `string` | `''` |  | Value of the input element. |
| `warningText?` | `string` |  |  | Warning text below the input field. |

### `IxTimePicker` (`<ix-time-picker>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `corners` | `TimePickerCorners` | `'rounded'` |  | Corner style. |
| `dateTimePickerAppearance` | `boolean` | `false` |  |  |
| `embedded` | `boolean` | `false` |  | Embedded style (for use in other components). |
| `format` | `string` | `'TT'` |  | Format of time string. See {@link https://moment.github.io/luxon/#/formatting?id=table-of-tokens} for all available tokens. Note: Formats that combine date and time (like f or F) are not supported. Timestamp tokens x and X are not supported either. |
| `getCurrentTime` | `() => Promise<string \| undefined>` |  |  | Get the current time based on the wanted format |
| `hideHeader` | `boolean` | `false` | 3.2.0 | Hides the header of the picker. |
| `hourInterval` | `number` | `1` | 3.2.0 | Interval for hour selection. |
| `i18nConfirmTime` | `string` | `'Confirm'` |  | Text of the time confirm button. |
| `i18nHeader` | `string` | `'Time'` |  | Text for the top header. |
| `i18nHourColumnHeader` | `string` | `'hr'` |  | Text for the hour column header. |
| `i18nMillisecondColumnHeader` | `string` | `'ms'` |  | Text for the millisecond column header. |
| `i18nMinuteColumnHeader` | `string` | `'min'` |  | Text for the minute column header. |
| `i18nSecondColumnHeader` | `string` | `'sec'` |  | Text for the second column header. |
| `maxTime?` | `string` |  | 5.0.0 | Latest selectable time (`format` tokens). Invalid non-empty values are ignored. |
| `millisecondInterval` | `number` | `100` | 3.2.0 | Interval for millisecond selection. |
| `minTime?` | `string` |  | 5.0.0 | Earliest selectable time (`format` tokens). Invalid non-empty values are ignored. |
| `minuteInterval` | `number` | `1` | 3.2.0 | Interval for minute selection. |
| `secondInterval` | `number` | `1` | 3.2.0 | Interval for second selection. |
| `time?` | `string` |  |  | Selected time value. Format has to match the `format` property. |

### `IxToggle` (`<ix-toggle>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `checked` | `boolean` | `false` |  | Whether the slide-toggle element is checked or not. |
| `disabled` | `boolean` | `false` |  | Whether the slide-toggle element is disabled or not. |
| `getAssociatedFormElement` | `() => Promise<HTMLFormElement \| null>` |  |  |  |
| `hasValidValue` | `() => Promise<boolean>` |  |  |  |
| `hideText` | `boolean` | `false` |  | Hide `on` and `off` text |
| `indeterminate` | `boolean` | `false` |  | If true the control is in indeterminate state |
| `isTouched` | `() => Promise<boolean>` |  |  |  |
| `name?` | `string` |  |  | Name of the checkbox component |
| `required` | `boolean` | `false` |  | Required state of the checkbox component. If true, checkbox needs to be checked to be valid |
| `textIndeterminate` | `string` | `'Mixed'` |  | Text for indeterminate state |
| `textOff` | `string` | `'Off'` |  | Text for off state |
| `textOn` | `string` | `'On'` |  | Text for on state |
| `value` | `string` | `'on'` |  | Value of the checkbox component |

### `IxUpload` (`<ix-upload>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `accept?` | `string` |  |  | The accept attribute specifies the types of files that the server accepts (that can be submitted through a file upload). See {@link https://www.w3schools.com/tags/att_input_accept.asp} |
| `directoryUpload` | `boolean` | `false` | 5.1.0 | If directoryUpload is true the user can drop or select a folder containing one or more files |
| `disabled` | `boolean` | `false` |  | Disable all input events |
| `i18nUploadDisabled` | `string` | `'File` |  | Text for disabled state  upload currently not possible.' |
| `i18nUploadFile?` | `string` |  |  | Label for upload file or folder button |
| `loadingText?` | `string` |  |  | Will be used by state = UploadFileState.LOADING |
| `multiline` | `boolean` | `false` |  | Whether the text should wrap to more than one line |
| `multiple` | `boolean` | `false` |  | If multiple is true the user can drop or select multiple files |
| `selectFileText?` | `string` |  |  | Will be used by state = UploadFileState.SELECT_FILE |
| `setFilesToUpload` | `(obj: any) => Promise<void>` |  |  | Set files @param obj |
| `state` | `UploadFileState` | `UploadFileState.SELECT_FILE` |  | After a file is uploaded you can set the upload component to a defined state |
| `uploadFailedText` | `string` | `'Upload` |  | Will be used by state = UploadFileState.UPLOAD_FAILED  failed. Please try again.' |
| `uploadSuccessText` | `string` | `'Upload` |  | Will be used by state = UploadFileState.UPLOAD_SUCCESSED  successful' |

## Layout & Structure (15)

### `IxApplication` (`<ix-application>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `appSwitchConfig?` | `AppSwitchConfiguration` |  |  | Define application switch configuration |
| `breakpoints` | `Breakpoint[]` | `['sm',` |  | Supported layouts  'md', 'lg'] |
| `colorSchema?` | `ThemeVariant` | `'system'` | 5.0.0 | Color schema of the theme |
| `forceBreakpoint` | `Breakpoint \| undefined` |  |  | Change the responsive layout of the menu structure |
| `theme?` | `string` |  |  | Application theme |

### `IxApplicationHeader` (`<ix-application-header>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `appIcon?` | `string` |  | 4.0.0 | The app icon will be shown as the first element inside the header. It will be hidden on smaller screens. |
| `appIconAlt?` | `string` |  | 4.0.0 | Alt text for the app icon |
| `appIconOutline` | `boolean` | `false` | 4.0.0 | Render subtle outline around app icon to ensure proper contrast. |
| `ariaLabelAppSwitchIconButton?` | `string` |  | 3.2.0 | ARIA label for the app switch icon button |
| `ariaLabelMoreMenuIconButton?` | `string` |  | 3.2.0 | ARIA label for the more menu icon button |
| `companyLogo?` | `string` |  | 4.0.0 | Company logo will be show on the left side of the application name. It will be hidden on smaller screens. |
| `companyLogoAlt?` | `string` |  | 4.0.0 | Alt text for the company logo |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `hideBottomBorder` | `boolean` | `false` | 4.0.0 | Hides the bottom border of the header |
| `name?` | `string` |  |  | Application name |
| `nameSuffix?` | `string` |  | 4.0.0 | Define a suffix which will be displayed next to the application name |
| `showMenu?` | `boolean` | `false` |  | Controls the visibility of the menu toggle button based on the context of the application header. When the application header is utilized outside the application frame, the menu toggle button is displayed. Conversely, if the header is within the application frame, this property is ineffective. |

### `IxCol` (`<ix-col>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `size?` | `ColumnSize` |  |  | Size of the column |
| `sizeLg?` | `ColumnSize` |  |  | Size of the column for lg screens |
| `sizeMd?` | `ColumnSize` |  |  | Size of the column for md screens |
| `sizeSm?` | `ColumnSize` |  |  | Size of the column for sm screens |

### `IxContent` (`<ix-content>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxContentHeader` (`<ix-content-header>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `hasBackButton` | `boolean` | `false` |  | Display a back button |
| `headerSubtitle` | `string \| undefined` | `undefined` |  | Subtitle of Header |
| `headerTitle?` | `string` |  |  | Title of Header |
| `variant` | `ContentHeaderVariant` | `'primary'` |  | Variant of content header |

### `IxDivider` (`<ix-divider>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxGroup` (`<ix-group>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `expandOnHeaderClick` | `boolean` | `false` |  | Expand the group if the header is clicked |
| `expanded` | `boolean` | `false` |  | Whether the group is expanded or collapsed. Defaults to false. |
| `header?` | `string` |  |  | Group header |
| `index?` | `number` |  |  | The index of the selected group entry. If undefined no group item is selected. |
| `selected` | `boolean` | `false` |  | Whether the group is selected. |
| `subHeader?` | `string` |  |  | Group header subtitle |
| `suppressHeaderSelection` | `boolean` | `false` |  | Prevent header from being selectable |

### `IxGroupContextMenu` (`<ix-group-context-menu>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxGroupItem` (`<ix-group-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelIcon?` | `string` |  |  | ARIA label for the icon |
| `disabled` | `boolean` | `false` |  | Disable the group item. The elements tabindex attribute will get set accordingly. If false tabindex will be 0, -1 otherwise. |
| `groupFooter` | `boolean` | `false` |  |  |
| `icon?` | `string` |  |  | Group item icon |
| `index?` | `number` |  |  | Index |
| `secondaryText?` | `string` |  |  | Group item secondary text |
| `selected` | `boolean` | `false` |  | Show selected state |
| `suppressSelection` | `boolean` | `false` |  | Supress the selection of the group |
| `text?` | `string` |  |  | Group item text |

### `IxLayoutAuto` (`<ix-layout-auto>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `layout` | `{
    minWidth: string` | `[` |  | Defines the layout of the form.  { minWidth: '0', columns: 1 }, { minWidth: '48em', columns: 2 }, ] |

### `IxLayoutGrid` (`<ix-layout-grid>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `columns` | `number` | `12` |  | Overwrite the default number of columns. Choose between 2 and 12 columns. |
| `gap` | `'8' \| '12' \| '16' \| '24'` | `'24'` |  | Grid gap |
| `noMargin` | `boolean` | `false` |  | The grid will not have any horizontal padding |

### `IxPane` (`<ix-pane>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCollapseCloseButton?` | `string` |  |  | ARIA label close or collapse button |
| `ariaLabelIcon?` | `string` |  |  | ARIA label for the icon |
| `borderless` | `boolean` | `false` |  | Toggle the border of the pane. Defaults to the borderless attribute of the pane layout. If used standalone it defaults to false. |
| `closeOnClickOutside` | `boolean` | `false` |  | If true, the pane will close when clicking outside of it |
| `composition` | `Composition` | `'top'` |  | Defines the position of the pane inside it's container. Inside a pane layout this property will automatically be set to the name of slot the pane is assigned to. |
| `expanded` | `boolean` | `false` |  | State of the pane |
| `heading?` | `string` |  |  | Title of the side panel |
| `hideOnCollapse` | `boolean` | `false` |  | Define if the pane should have a collapsed state |
| `icon?` | `string` |  |  | Name of the icon |
| `ignoreLayoutSettings` | `boolean` | `false` |  |  |
| `isMobile` | `boolean` | `false` |  |  |
| `noPadding` | `boolean` | `false` | 5.1.0 | Remove the padding of the content area. If set to `true` the left, right and bottom padding of the content area is removed. |
| `size` | `\| '240px'
    \| '320px'
    \| '360px'
    \| '480px'
    \| '600px'
    \| '33%'
    \| '50%'` | `'240px'` |  | The maximum size of the sidebar, when it is expanded |
| `variant` | `'floating' \| 'inline'` | `'inline'` |  | Variant of the side pane. Defaults to the variant attribute of the pane layout. If used standalone it defaults to inline. |

### `IxPaneLayout` (`<ix-pane-layout>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `borderless` | `boolean` | `false` |  | Set the default border state for all panes in the layout |
| `layout` | `'full-vertical' \| 'full-horizontal'` | `'full-vertical'` |  | Choose the layout of the panes. When set to 'full-vertical' the vertical panes (left, right) will get the full height. When set to 'full-horizontal' the horizontal panes (top, bottom) will get the full width. |
| `variant` | `'floating' \| 'inline'` | `'inline'` |  | Set the default variant for all panes in the layout |

### `IxRow` (`<ix-row>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxSpinner` (`<ix-spinner>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `hideTrack` | `boolean` | `false` |  |  |
| `size` | `'xx-small' \| 'x-small' \| 'small' \| 'medium' \| 'large'` | `'medium'` |  | Size of spinner |
| `variant` | `'primary' \| 'secondary'` | `'secondary'` |  | Variant of spinner |

## Navigation (20)

### `IxBreadcrumb` (`<ix-breadcrumb>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelPreviousButton` | `string` | `'Show` |  | Accessibility label for the dropdown button (ellipsis icon) used to access the dropdown list with conditionally hidden previous items  previous breadcrumb items' |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `nextItems` | `BreadcrumbClick[]` | `[]` | 5.0.0 | Items will be accessible through a dropdown |
| `subtle` | `boolean` | `false` |  | Ghost breadcrumbs will not show solid backgrounds on individual crumbs unless there is a mouse event (e.g. hover) |
| `visibleItemCount` | `number` | `9` |  | Excess items will get hidden inside of dropdown |

### `IxBreadcrumbItem` (`<ix-breadcrumb-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `breadcrumbKey` | `string` |  | 5.0.0 | Will be used as the key for the breadcrumb item, which will be emitted in the itemClick event when the breadcrumb item is clicked. |
| `hideChevron` | `boolean` | `false` |  |  |
| `href?` | `string` |  | 4.0.0 | URL for the button link. When provided, the button will render as an anchor tag. |
| `icon?` | `string` |  |  | Icon to be displayed next ot the label |
| `invisible` | `boolean` | `false` |  |  |
| `isCurrentPage` | `boolean` | `false` |  |  |
| `isDropdownTrigger` | `boolean` | `false` |  |  |
| `label?` | `string` |  |  | Breadcrumb label |
| `rel?` | `string` |  | 4.0.0 | Specifies the relationship between the current document and the linked document when href is provided. |
| `subtle` | `boolean` | `false` |  |  |
| `target?` | `AnchorTarget` | `'_self'` | 4.0.0 | Specifies where to open the linked document when href is provided. |

### `IxCategoryFilter` (`<ix-category-filter>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelFilterInput?` | `string` |  | 3.2.0 | ARIA label for the filter input Will be set as aria-label on the nested HTML input element |
| `ariaLabelOperatorButton?` | `string` |  | 3.2.0 | ARIA label for the operator button Will be set as aria-label on the nested HTML button element |
| `ariaLabelResetButton?` | `string` |  | 3.2.0 | ARIA label for the reset button Will be set as aria-label on the nested HTML button element |
| `categories?` | `{
    [id: string]: {
      label: string` |  |  | Configuration object hash used to populate the dropdown menu for type-ahead and quick selection functionality. Each ID maps to an object with a label and an array of options to select from. |
| `disabled` | `boolean` | `false` |  | If true the filter will be in disabled state |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `filterState?` | `FilterState` |  |  | A set of search criteria to populate the component with. |
| `hideIcon` | `boolean` | `false` |  | Allows to hide the icon inside the text input. Defaults to false |
| `i18nPlainText` | `string` | `'Filter` |  | i18n label for 'Filter by text'  by text' |
| `icon?` | `string` |  |  | The icon next to the actual text input Defaults to 'search' |
| `labelCategories` | `string` | `'Categories'` |  | i18n |
| `nonSelectableCategories?` | `{
    [id: string]: string` | `{}` |  | In certain use cases some categories may not be available for selection anymore. To allow proper display of set filters with these categories this ID to label mapping can be populated. Configuration object hash used to supply labels to the filter chips in the input field. Each ID maps to a string representing the label to display. |
| `placeholder?` | `string` |  |  | Placeholder text to be displayed in an empty input field. |
| `readonly` | `boolean` | `false` |  | If true the filter will be in readonly mode |
| `staticOperator?` | `LogicalFilterOperator` |  |  | If set categories will always be filtered via the respective logical operator. Toggling of the operator will not be available to the user. |
| `suggestions?` | `string[]` |  |  | A list of strings that will be supplied as type-ahead suggestions not tied to any categories. |
| `uniqueCategories` | `boolean` | `false` |  | If set to true, prevents that a single category can be set more than once. An already set category will not appear in the category dropdown if set to true. |

### `IxDropdown` (`<ix-dropdown>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `anchor?` | `ElementReference` |  |  | Define an anchor element |
| `callbackFocusElement?` | `(
    event: KeyboardEvent
  ) => Promise<boolean \| undefined>` |  |  |  |
| `closeBehavior` | `CloseBehavior` | `'both'` |  | Controls if the dropdown will be closed in response to a click event depending on the position of the event relative to the dropdown. If the dropdown is a child of another one, it will be closed with the parent, regardless of its own close behavior. |
| `disableFocusHandling` | `boolean` | `false` | 4.3.0 | Suppress automatic focus when the dropdown is shown |
| `disableFocusTrap` | `boolean` | `false` | 4.3.0 | Close dropdown when tabbing away, and do not trap focus inside dropdown |
| `discoverAllSubmenus` | `boolean` | `false` |  |  |
| `discoverSubmenu` | `() => Promise<void>` |  |  |  |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for top-layer positioning.  in v5.x, will default to true in v6.0.0 |
| `focusCheckedItem` | `boolean` | `false` | 5.0.0 | If true, the dropdown will try to focus checked items first when opened via keyboard, otherwise it will always focus the first focusable item. |
| `focusHost?` | `HTMLElement` |  |  |  |
| `focusTrapOptions?` | `FocusTrapOptions` |  |  |  |
| `header?` | `string` |  |  | An optional header shown at the top of the dropdown |
| `hostRole?` | `string` |  |  |  |
| `ignoreRelatedSubmenu` | `boolean` | `false` |  |  |
| `keyboardActivationKeys` | `string[]` | `[` |  | Keys that will open the dropdown when the trigger is focused  'Home', 'End', 'ArrowDown', 'ArrowUp', 'Enter', ' ', ] |
| `keyboardItemTriggerKeys` | `string[]` | `['Enter',` |  | Keys that will open the dropdown when the trigger is focused  ' '] |
| `offset?` | `{
    mainAxis?: number` |  |  | Move dropdown along main axis of alignment |
| `overwriteDropdownStyle?` | `(delegate: {
    dropdownRef: HTMLElement` |  |  |  |
| `placement` | `AlignedPlacement` | `'bottom-start'` |  | Placement of the dropdown |
| `positioningStrategy` | `'absolute' \| 'fixed'` | `'fixed'` |  | Position strategy |
| `resetForwardQueryElement` | `() => Promise<void>` |  |  |  |
| `show` | `boolean` | `false` |  | Show dropdown |
| `suppressAutomaticPlacement` | `boolean` | `false` |  | Suppress the automatic placement of the dropdown. |
| `suppressOverflowBehavior` | `boolean` | `false` |  |  |
| `suppressTriggerVisibilityCheck` | `boolean` | `false` | 5.0.0 | By default the dropdown gets closed if the trigger is not visible anymore (e.g. due to scrolling). Setting this property prevents that behavior. |
| `trigger?` | `ElementReference` |  |  | Define an element that triggers the dropdown. A trigger can either be a string that will be interpreted as id attribute or a DOM element. |
| `updatePosition` | `() => Promise<void>` |  |  | Update position of dropdown |

### `IxDropdownHeader` (`<ix-dropdown-header>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `label?` | `string` |  |  | Display name of the header |

### `IxDropdownItem` (`<ix-dropdown-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelButton?` | `string` |  | 3.2.0 | ARIA label for the item's button Will be set as aria-label for the nested HTML button element |
| `ariaLabelIcon?` | `string` |  |  | ARIA label for the icon |
| `checked` | `boolean` | `false` |  | Whether the item is checked or not. If true a checkmark will mark the item as checked. |
| `disableAriaSelectHandling` | `boolean` | `false` |  | When `true`, do not map keyboard focus visibility to `aria-selected` on the host. Use when selection state must not mirror roving focus (e.g. `ix-select-item`). |
| `disabled` | `boolean` | `false` |  | Disable item and remove event listeners |
| `emitItemClick` | `() => Promise<void>` |  |  |  |
| `getDropdownItemElement` | `() => Promise<HTMLIxDropdownItemElement>` |  |  |  |
| `hasVisualFocus` | `boolean` | `false` |  |  |
| `hover` | `boolean` | `false` |  | Display hover state |
| `icon?` | `string` |  |  | Icon of dropdown item |
| `isSubMenu` | `boolean` | `false` |  |  |
| `itemRole` | `IxDropdownItemRole` | `'menuitem'` | 5.0.0 | Role of the host surface. Use `option` when the item represents a listbox option (e.g. inside select); use `menuitem` in menus. |
| `ixFocusVisible` | `boolean` | `false` |  |  |
| `label?` | `string` |  |  | Label of dropdown item |
| `suppressChecked` | `boolean` | `false` |  |  |

### `IxDropdownQuickActions` (`<ix-dropdown-quick-actions>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxMenu` (`<ix-menu>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `applicationDescription` | `string` | `''` |  | Should only be set if you use ix-menu standalone |
| `applicationName?` | `string` |  |  | Should only be set if you use ix-menu standalone |
| `enableToggleTheme` | `boolean` | `false` |  | Show toggle between light and dark variant. Only if the provided theme have implemented both! |
| `expand` | `boolean` | `false` |  | Toggle the expand state of the menu |
| `i18nAriaLabelMenu` | `string` | `'Application` | 5.1.0 | i18n aria-label for menu. Gets read out by screen readers when first focusing the menu   Navigation' |
| `i18nCollapse` | `string` | `'Collapse'` |  | i18n label for 'Collapse' button |
| `i18nExpand` | `string` | `'Expand'` |  | i18n label for 'Expand' button |
| `i18nLegal` | `string` | `'About` |  | i18n label for 'About & legal information' button  & legal information' |
| `i18nNavigationHint` | `string` | `'Use` | 5.1.0 | i18n description for menu keyboard navigation hint, read by screen readers when focusing the menu   Up and Down arrow keys to navigate between menu items' |
| `i18nSettings` | `string` | `'Settings'` |  | i18n label for 'Settings' button |
| `i18nToggleTheme` | `string` | `'Toggle` |  | i18n label for 'Toggle theme' button  theme' |
| `pinned` | `boolean` | `false` |  | Menu stays pinned to the left |
| `showAbout` | `boolean` | `false` |  | Is about tab visible |
| `showSettings` | `boolean` | `false` |  | Is settings tab visible |
| `startExpanded` | `boolean` | `false` |  | If set the menu will be expanded initially. This will only take effect at the breakpoint 'lg'. |
| `toggleAbout` | `(show: boolean) => Promise<void>` |  |  | Toggle About tabs @param show |
| `toggleMapExpand` | `(show?: boolean) => Promise<void>` |  |  | Toggle map sidebar expand @param show |
| `toggleMenu` | `(show?: boolean) => Promise<void>` |  |  | Toggle menu @param show |
| `toggleSettings` | `(show: boolean) => Promise<void>` |  |  | Toggle Settings tabs @param show |

### `IxMenuAbout` (`<ix-menu-about>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `activeTabKey?` | `string` |  | 5.0.0 | Active tab used for legacy ix-menu-about-item integrations @deprecated since 5.0.0, only used for legacy ix-menu-about-item integrations |
| `ariaLabelCloseButton` | `string` | `'Close` |  | Aria label for close button  About' |
| `label` | `string` | `'About` |  | Content of the header  & legal information' |
| `show` | `boolean` | `false` |  |  |
| `suppressLegacyTabs` | `boolean` | `false` | 5.0.0 | Whether to suppress legacy tabs (ix-menu-about-item) and use slotted tabs (ix-tab-item) instead |

### `IxMenuAboutItem` (`<ix-menu-about-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `label?` | `string` |  |  | About Item label |
| `tabKey` | `string` |  | 5.0.0 | Key of the tab, used for identifying the tab in events |

### `IxMenuAboutNews` (`<ix-menu-about-news>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `aboutItemLabel?` | `string` |  |  | Subtitle of the about news |
| `activeAboutTabKey?` | `string` |  | 5.0.0 | Defines which tab should be active, used when the about news is used in combination with ix-menu-about |
| `expanded` | `boolean` | `false` |  |  |
| `i18nShowMore` | `string` | `'Show` |  | i18n label for 'Show more' button  more' |
| `label?` | `string` |  |  | Title of the about news |
| `show` | `boolean` | `false` |  | Show about news |

### `IxMenuAvatar` (`<ix-menu-avatar>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelTooltip?` | `string` |  | 4.3.0. | aria-label for the tooltip |
| `bottom?` | `string` |  |  | Second line of text |
| `enableTopLayer` | `boolean` | `false` | 4.3.0 | Enable Popover API rendering for dropdown. |
| `hideLogoutButton` | `boolean` | `false` |  | Control the visibility of the logout button |
| `i18nLogout` | `string` | `'Logout'` |  | i18n label for 'Logout' button |
| `image?` | `string` |  |  | Display a avatar image |
| `initials?` | `string` |  |  | Display the initials of the user. Will be overwritten by image |
| `tooltipText?` | `string` |  | 4.3.0. | Tooltip text to display on hover. If not set, the 'top' property (user name) will be used as the default tooltip text. |
| `top?` | `string` |  |  | First line of text |

### `IxMenuAvatarItem` (`<ix-menu-avatar-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `getDropdownItemElement` | `() => Promise<HTMLIxDropdownItemElement>` |  |  |  |
| `icon?` | `string` |  |  | Avatar dropdown icon |
| `label?` | `string` |  |  | Avatar dropdown label |

### `IxMenuItem` (`<ix-menu-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `active` | `boolean` | `false` |  | State to display active |
| `bottom` | `boolean` | `false` |  | Caution: this is no longer working. Please use slot="bottom" instead. Place tab on bottom |
| `disabled` | `boolean` | `false` |  | Disable tab and remove event handlers |
| `home` | `boolean` | `false` |  | Move the Tab to a top position. |
| `href?` | `string` |  | 4.0.0 | URL for the button link. When provided, the button will render as an anchor tag. |
| `icon?` | `string` |  |  | Name of the icon you want to display. Icon names can be resolved from the documentation {@link https://ix.siemens.io/docs/icon-library/icons} |
| `isCategory` | `boolean` | `false` |  |  |
| `label?` | `string` |  |  | Label of the menu item. Will also be used as tooltip text |
| `menuCategoryLabel?` | `string` |  |  |  |
| `notifications?` | `number` |  |  | Show notification count on tab |
| `rel?` | `string` |  | 4.0.0 | Specifies the relationship between the current document and the linked document when href is provided. |
| `setTabIndex` | `(value: number) => Promise<void>` |  |  |  |
| `target?` | `AnchorTarget` | `'_self'` | 4.0.0 | Specifies where to open the linked document when href is provided. |
| `tooltipText?` | `string` |  | 4.0.0 | Will be shown as tooltip text, if not provided menu text content will be used. |

### `IxMenuSettings` (`<ix-menu-settings>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `activeTabKey?` | `string` |  | 5.0.0 | Active tab used for legacy ix-menu-settings-item integrations @deprecated since 5.0.0, only used for legacy ix-menu-settings-item integrations |
| `ariaLabelCloseButton` | `string` | `'Close` |  | Aria label for close button  Settings' |
| `label` | `string` | `'Settings'` |  | Label of first tab |
| `show` | `boolean` | `false` |  |  |
| `suppressLegacyTabs` | `boolean` | `false` | 5.0.0 | Whether to suppress legacy tabs (ix-menu-settings-item) and use slotted tabs (ix-tab-item) instead |

### `IxPagination` (`<ix-pagination>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `advanced` | `boolean` | `false` |  | Advanced mode |
| `ariaLabelChevronLeftIconButton?` | `string` | `'Previous` | 3.2.0 | ARIA label for the chevron left icon button Will be set as aria-label on the nested HTML button element   page' |
| `ariaLabelChevronRightIconButton?` | `string` | `'Next` | 3.2.0 | ARIA label for the chevron right icon button Will be set as aria-label on the nested HTML button element   page' |
| `ariaLabelPageSelection` | `string` | `'Page` | 4.1.0 | ARIA label for the page selection input Will be set as aria-label on the nested HTML input element   selection input' |
| `count` | `number` | `0` |  | Total number of pages |
| `hideItemCount` | `boolean` | `false` |  | Hide item count in advanced mode |
| `i18nItems` | `string` | `'Items'` |  | i18n label for 'Items' |
| `i18nOf` | `string` | `'of'` |  | i18n label for 'of' |
| `i18nPage` | `string` | `'Page'` |  | i18n label for 'Page' |
| `itemCount` | `number` | `15` |  | Number of items shown at once. Can only be changed in advanced mode. |
| `itemCountOptions` | `number[]` | `[10,` | 4.4.0 | Custom item count options for advanced mode. Provide an array of positive numbers to display in the items per page dropdown.   15, 20, 40, 100] |
| `selectedPage` | `number` | `0` |  | Zero based index of currently selected page |

### `IxTabItem` (`<ix-tab-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCloseButton` | `string` | `'Close` | 5.0.0 | Aria label for the close button, important for accessibility   tab' |
| `closable` | `boolean` | `false` | 5.0.0 | If the tab can be closed |
| `counter?` | `number` |  |  | Set counter value |
| `disabled` | `boolean` | `false` |  | Set disabled tab |
| `icon?` | `string` |  | 5.0.0 | Set icon of the tab |
| `iconOnly` | `boolean` | `false` |  |  |
| `label?` | `string` |  | 5.0.0 | Tab label |
| `layout` | `'auto' \| 'stretched'` | `'auto'` |  |  |
| `placement` | `'bottom' \| 'top'` | `'bottom'` |  |  |
| `rounded` | `boolean` | `false` |  |  |
| `selected` | `boolean` | `false` |  | Set selected tab |
| `small` | `boolean` | `false` |  |  |
| `tabKey` | `string` |  | 5.0.0 | Key of the tab, used for identifying the tab in events |

### `IxTabs` (`<ix-tabs>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `activeTabKey?` | `string` |  | 5.0.0 | Active tab key. |
| `ariaLabelMoreTabs` | `string` | `'Show` | 5.0.0 | Aria label for the overflow menu button.   all tabs' |
| `keyboardNavigation` | `'automatic' \| 'manual'` | `'automatic'` | 5.0.0 | Keyboard interaction behavior: automatic: A tabs widget where tabs are automatically activated and their panel is displayed when they receive focus. manual: A tabs widget where users activate a tab and display its panel by pressing Space or Enter. |
| `layout` | `'auto' \| 'stretched'` | `'auto'` |  | Set layout width style |
| `placement` | `'bottom' \| 'top'` | `'bottom'` |  | Set placement style |
| `rounded` | `boolean` | `false` |  | Set rounded tabs |
| `small` | `boolean` | `false` |  | Set tab items to small size |

### `IxWorkflowStep` (`<ix-workflow-step>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `clickable` | `boolean` | `false` |  | Activate navigation click |
| `disabled` | `boolean` | `false` |  | Set disabled |
| `position` | `'first' \| 'last' \| 'single' \| 'undefined'` | `'undefined'` |  | Activate navigation click |
| `selected` | `boolean` | `false` |  | Set selected |
| `status` | `'open' \| 'success' \| 'done' \| 'warning' \| 'error'` | `'open'` |  | Set status |
| `vertical` | `boolean` | `false` |  | Select orientation |

### `IxWorkflowSteps` (`<ix-workflow-steps>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `clickable` | `boolean` | `false` |  | Activate navigation click |
| `selectedIndex` | `number` | `0` |  | Activate navigation click |
| `vertical` | `boolean` | `false` |  | Select orientation |

## Data Display (18)

### `IxActionCard` (`<ix-action-card>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCard?` | `string` |  | 3.2.0 | ARIA label for the card |
| `ariaLabelIcon?` | `string` |  | 3.2.0 | ARIA label for the icon |
| `heading?` | `string` |  |  | Card heading |
| `icon` | `string \| undefined` | `undefined` |  | Card icon |
| `passive` | `boolean` | `false` |  | If true, disables hover and active styles and changes cursor to default |
| `selected` | `boolean` | `false` |  | Card selection |
| `subheading?` | `string` |  |  | Card subheading |
| `variant` | `ActionCardVariant` | `'outline'` |  | Card variant |

### `IxAvatar` (`<ix-avatar>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelTooltip?` | `string` |  | 4.0.0 | aria-label for the tooltip |
| `extra?` | `string` |  |  | Optional description text that will be displayed underneath the username. Note: Only working if avatar is part of the ix-application-header |
| `image?` | `string` |  |  | Display an avatar image |
| `initials?` | `string` |  |  | Display the initials of the user. Will be overwritten by image |
| `tooltipText?` | `string` |  | 4.0.0 | Text to display in a tooltip when hovering over the avatar |
| `username?` | `string` |  |  | If set an info card displaying the username will be placed inside the dropdown. Note: Only working if avatar is part of the ix-application-header |

### `IxCard` (`<ix-card>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `passive` | `boolean` | `false` |  | If true, disables hover and active styles and changes cursor to default |
| `selected` | `boolean` | `false` |  | Show card in selected state |
| `variant` | `CardVariant` | `'outline'` |  | Card variant |

### `IxCardAccordion` (`<ix-card-accordion>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelExpandButton?` | `string` |  | 3.2.0 | ARIA label for the card's expand button. Will be set as aria-label on the nested HTML button element |
| `collapse` | `boolean` | `false` |  | Collapse the card |
| `variant` | `CardAccordionVariant` | `'outline'` | 4.0.0 | Show accordion with different color variants |

### `IxCardContent` (`<ix-card-content>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxCardList` (`<ix-card-list>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelExpandButton?` | `string` |  | 3.2.0 | ARIA label for the card's expand button. Will be set as aria-label on the nested HTML button element |
| `collapse` | `boolean` | `false` |  | Collapse the list |
| `hideShowAll` | `boolean` | `false` |  | Hide the show all button |
| `i18nMoreCards` | `string` | `'There` |  | i18n More cards available  are more cards available' |
| `i18nShowAll` | `string` | `'Show` |  | i18n Show all button  all' |
| `i18nShowLess` | `string` | `'Show` | 5.0.0 | i18n show less button   less' |
| `label?` | `string` |  |  | Name the card list |
| `listStyle` | `'stack' \| 'scroll'` | `'stack'` |  | List style |
| `maxVisibleCards` | `number` | `12` |  | Maximal visible cards |
| `showAllCount?` | `number` |  |  | Overwrite the default show all count. |
| `suppressOverflowHandling` | `boolean` | `false` |  | Suppress the overflow handling of child elements |

### `IxCardTitle` (`<ix-card-title>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxChip` (`<ix-chip>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCloseButton?` | `string` | `'Close` |  | ARIA label for the close button Will be set as aria-label on the nested HTML button element  chip' |
| `ariaLabelIcon?` | `string` |  | 5.0.0 | Accessible name for the leading icon. When unset, the icon is treated as decorative (hidden from assistive tech) when the default slot supplies a visible label. |
| `background` | `string \| undefined` |  |  | Custom background color. Only has an effect on chips with `variant='custom'` |
| `centerContent` | `boolean` | `false` | 3.2.0 | Center the content of the chip. Set to false to disable centering. |
| `chipColor` | `string \| undefined` |  |  | Custom font and icon color. Only has an effect on chips with `variant='custom'` |
| `closable` | `boolean` | `false` |  | Show close icon |
| `icon?` | `string` |  |  | Show icon |
| `inactive` | `boolean` | `false` |  | Determines if the chip is interactive. If true no user input (e.g. mouse states, keyboard navigation) will be possible and also the close button will not be present. |
| `outline` | `boolean` | `false` |  | Show chip with outline style |
| `tooltipText` | `string \| boolean` | `false` | 3.0.0 | Display a tooltip. By default, no tooltip will be displayed. Add the attribute to display the text content of the component as a tooltip or use a string to display a custom text. |
| `variant` | `ChipVariant` | `'primary'` |  | Chip variant. Defaults to `primary`. When unset or set to an unknown value the chip falls back to `primary` styling. |

### `IxEventList` (`<ix-event-list>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `animated` | `boolean` | `false` |  | Animate state change transitions. Defaults to 'false'. |
| `chevron` | `boolean` | `false` |  | Display a chevron icon in list items. Defaults to 'false' |
| `compact` | `boolean` | `false` |  | Make event-list items more compact |
| `itemHeight` | `'S' \| 'L' \| number` | `'S'` |  | Determines the height of list items. This can either be one of two predefined sizes ('S' or 'L') or an absolute pixel value. In case a number is supplied it will get converted to rem internally. Defaults to 'S'. |

### `IxEventListItem` (`<ix-event-list-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `chevron` | `boolean` | `false` |  | Show chevron on right side of the event list item |
| `disabled` | `boolean` | `false` |  | Disable event list item |
| `itemColor?` | `string` |  |  | Color of the status indicator. You can find a list of all available colors in our documentation. Example values are `--theme-color-alarm` or `color-alarm` {@link https://ix.siemens.io/docs/styles/colors} |
| `selected` | `boolean` | `false` |  | Show event list item as selected |
| `variant` | `'outline' \| 'filled'` | `'outline'` | 4.0.0 | Variant of the event list item |

### `IxFilterChip` (`<ix-filter-chip>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCloseIconButton?` | `string` |  |  | ARIA label for the close icon button Will be set as aria-label on the nested HTML button element |
| `disabled` | `boolean` | `false` |  | If true the filter chip will be in disabled state |
| `hideCloseButton` | `boolean` | `false` |  | If true the close button will not be rendered. Primarily used for overflow chip. |
| `readonly` | `boolean` | `false` |  | If true the filter chip will be in readonly mode |

### `IxFlipTile` (`<ix-flip-tile>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelEyeIconButton?` | `string` |  | 3.2.0 | ARIA label for the eye icon button Will be set as aria-label on the nested HTML button element |
| `height` | `number \| 'auto'` | `15.125` |  | Height interpreted as REM |
| `index` | `number` | `0` | 3.0.0 | Index of the currently visible content |
| `variant` | `FlipTileVariant` | `'filled'` | 4.0.0 | Variation of the Flip |
| `width` | `number \| 'auto'` | `16` |  | Width interpreted as REM |

### `IxFlipTileContent` (`<ix-flip-tile-content>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `contentVisible` | `boolean` | `false` |  | Controls the visibility of the content |

### `IxKeyValue` (`<ix-key-value>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelIcon?` | `string` |  | 3.2.0 | ARIA label for the icon |
| `icon?` | `string` |  |  | Optional key value icon |
| `label` | `string` |  |  | Key value label |
| `labelPosition` | `KeyValueLabelPosition` | `'top'` |  | Optional key value label position - 'top' or 'left' |
| `value?` | `string` |  |  | Optional key value text value |

### `IxKeyValueList` (`<ix-key-value-list>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `striped` | `boolean` | `false` |  | Optional striped key value list style |

### `IxKpi` (`<ix-kpi>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelAlarmIcon?` | `string` |  | 3.2.0 | ARIA label for the alarm icon |
| `ariaLabelWarningIcon?` | `string` |  | 3.2.0 | ARIA label for the warning icon |
| `label?` | `string` |  |  |  |
| `orientation` | `'horizontal' \| 'vertical'` | `'horizontal'` |  |  |
| `state` | `'neutral' \| 'warning' \| 'alarm'` | `'neutral'` |  |  |
| `unit?` | `string` |  |  |  |
| `value?` | `string \| number` |  |  |  |

### `IxTile` (`<ix-tile>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `size` | `'small' \| 'medium' \| 'big'` | `'medium'` |  | Size of the tile - one of 'small', 'medium' or 'large' |

### `IxTypography` (`<ix-typography>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `bold` | `boolean` | `false` |  | Display text bold |
| `format?` | `TypographyFormat` |  |  | Text format |
| `textColor?` | `TypographyColors` |  |  | Text color based on theme variables |
| `textDecoration` | `TextDecoration` | `'none'` |  | Text decoration |

## Feedback & Overlay (9)

### `IxBlind` (`<ix-blind>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `collapsed` | `boolean` | `false` |  | Collapsed state |
| `icon?` | `string` |  |  | Optional icon to be displayed next to the header label |
| `label?` | `string` |  |  | Label of blind |
| `sublabel?` | `string` |  |  | Secondary label inside blind header |
| `variant` | `BlindVariant` | `'filled'` |  | Blind variant |

### `IxEmptyState` (`<ix-empty-state>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `action?` | `string` |  |  | Optional empty state action |
| `ariaLabelEmptyStateIcon?` | `string` |  | 3.2.0 | ARIA label for the empty state icon |
| `header` | `string` |  |  | Empty state header |
| `icon?` | `string` |  |  | Optional empty state icon |
| `layout` | `EmptyStateLayout` | `'large'` |  | Optional empty state layout - one of 'large', 'compact' or 'compactBreak' |
| `subHeader?` | `string` |  |  | Optional empty state sub header |

### `IxMessageBar` (`<ix-message-bar>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `persistent` | `boolean` | `false` |  | If true, close button is disabled and alert cannot be dismissed by the user |
| `type` | `\| 'alarm'
    \| 'critical'
    \| 'warning'
    \| 'success'
    \| 'info'
    \| 'neutral'
    \| 'primary'` | `'info'` |  | Specifies the type of the alert. |

### `IxModal` (`<ix-modal>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `beforeDismiss?` | `(reason?: unknown) => boolean \| Promise<boolean>` |  |  | Is called before the modal is dismissed. - Return `true` to proceed in dismissing the modal - Return `false` to abort in dismissing the modal |
| `centered` | `boolean` | `false` |  | Centered modal |
| `closeModal` | `<T = unknown>(reason: T) => Promise<void>` |  |  | Close the dialog |
| `closeOnBackdropClick` | `boolean` | `false` |  | Dismiss modal on backdrop click (outside the dialog panel). Ignored when **isNonBlocking** is `true`. |
| `disableAnimation` | `boolean` | `false` |  | Should the modal animation be disabled |
| `dismissModal` | `<T = unknown>(reason?: T) => Promise<void>` |  |  | Dismiss the dialog |
| `hideBackdrop` | `boolean` | `false` |  | Hide the backdrop behind the modal dialog |
| `isNonBlocking` | `boolean` | `false` |  | Non-modal dialog: page stays interactive, no lightbox or focus trap; `aria-modal` is `false`. Set before calling `showModal()`; changing while open is unsupported. |
| `showModal` | `() => Promise<void>` |  |  | Show the dialog |
| `size` | `IxModalSize` | `'360'` |  | Modal size |

### `IxModalHeader` (`<ix-modal-header>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCloseIconButton?` | `string` | `'Close` | 3.2.0 | ARIA label for the close icon button Will be set as aria-label on the nested HTML button element   modal' |
| `ariaLabelIcon?` | `string` |  |  | ARIA label for the icon |
| `hideClose` | `boolean` | `false` |  | Hide the close button |
| `icon?` | `string` |  |  | Icon of the header |
| `iconColor?` | `string` |  |  | Icon color |

### `IxPopover` (`<ix-popover>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `closeOnClickOutside` | `boolean` | `false` | 5.1.0 | Dismiss when clicking outside the popover and trigger |
| `hasSpike` | `boolean` | `false` | 5.1.0 | Show the spike pointing at the trigger |
| `hidePopover` | `() => Promise<void>` |  | 5.1.0 | Close the popover programmatically |
| `placement` | `'top' \| 'bottom' \| 'left' \| 'right'` | `'bottom'` | 5.1.0 | Preferred placement relative to trigger |
| `show` | `boolean` | `false` | 5.1.0 | Show/hide state |
| `showPopover` | `() => Promise<void>` |  | 5.1.0 | Open the popover programmatically |
| `trigger?` | `ElementReference` |  | 5.1.0 | Element that toggles the popover. String values are resolved as the trigger element `id`, not as CSS selectors. Also accepts a DOM element reference. |
| `triggerMode` | `'click' \| 'hover'` | `'click'` | 5.1.0 | Interaction that opens the popover |

### `IxPopoverHeader` (`<ix-popover-header>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCloseIconButton?` | `string` | `'Close'` | 5.1.0 | ARIA label for the close icon button. Will be set as aria-label on the nested HTML button element. |
| `hideClose` | `boolean` | `false` | 5.1.0 | Hide the close (X) button |
| `icon?` | `string` |  | 5.1.0 | Icon name displayed before the title. The icon is decorative; provide context in the default slot heading. |
| `iconColor?` | `string` |  | 5.1.0 | Icon color |

### `IxToast` (`<ix-toast>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelCloseIconButton?` | `string` | `'Close` | 3.2.0 | ARIA label for the close icon button Will be set as aria-label on the nested HTML button element   toast' |
| `autoCloseDelay` | `number` | `5000` |  | Autoclose title after delay |
| `hideIcon` | `boolean` | `false` |  | Allows to hide the icon in the toast. |
| `icon?` | `string` |  |  | Icon of toast |
| `iconColor?` | `string` |  |  | Icon color of toast |
| `isPaused` | `() => Promise<boolean>` |  |  | Returns whether the toast is currently paused (auto-close is paused). |
| `pause` | `() => Promise<void>` |  |  | Pause the toast's auto-close progress bar and timer. |
| `preventAutoClose` | `boolean` | `false` |  | Autoclose behavior |
| `resume` | `() => Promise<void>` |  |  | Resume the toast's auto-close progress bar and timer if previously paused. |
| `toastTitle?` | `string` |  |  | Toast title |
| `type` | `ToastType` | `'info'` |  | Toast type |

### `IxTooltip` (`<ix-tooltip>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `animationFrame` | `boolean` | `false` |  |  |
| `for?` | `ElementReference \| ElementReference[]` |  |  | CSS selector for hover trigger element e.g. `for="[data-my-custom-select]"` |
| `hideDelay` | `number` | `50` |  |  |
| `hideTooltip` | `(hideDelay?: number) => Promise<void>` |  |  |  |
| `interactive` | `boolean` | `false` |  | Define if the user can access the tooltip via mouse. |
| `placement` | `'top' \| 'right' \| 'bottom' \| 'left'` | `'top'` |  | Initial placement of the tooltip. If the selected placement doesn't have enough space, the tooltip will be repositioned to another location. |
| `showDelay` | `number` | `0` |  |  |
| `showTooltip` | `(anchorElement: Element) => Promise<void>` |  |  |  |
| `titleContent?` | `string` |  |  | Title of the tooltip |

## Other (12)

### `IxMenuCategory` (`<ix-menu-category>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `icon?` | `string` |  |  | Icon of the category |
| `label?` | `string` |  |  | Display name of the category |
| `notifications?` | `number` |  |  | Show notification count on the category |
| `setTabIndex` | `(value: number) => Promise<void>` |  |  |  |
| `tooltipText?` | `string` |  | 4.0.0 | Will be shown as tooltip text, if not provided menu text content will be used. |

### `IxMenuSettingsItem` (`<ix-menu-settings-item>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `label?` | `string` |  |  | Settings Item label |
| `tabKey` | `string` |  | 5.0.0 | Key of the tab, used for identifying the tab in events |

### `IxModalContent` (`<ix-modal-content>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxModalFooter` (`<ix-modal-footer>`)

_No declared props found in components.d.ts (may be a pure layout/slot component)._

### `IxPill` (`<ix-pill>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `alignLeft` | `boolean` | `false` |  | Align pill content left |
| `ariaLabelIcon?` | `string` |  | 3.2.0 | ARIA label for the icon |
| `background` | `string \| undefined` |  |  | Custom color for pill. Only working for `variant='custom'` |
| `icon?` | `string` |  |  | Show icon |
| `outline` | `boolean` | `false` |  | Show pill as outline |
| `pillColor` | `string \| undefined` |  |  | Custom font color for pill. Only working for `variant='custom'` |
| `tooltipText` | `string \| boolean` | `false` | 3.0.0 | Display a tooltip. By default, no tooltip will be displayed. Add the attribute to display the text content of the component as a tooltip or use a string to display a custom text. |
| `variant` | `\| 'primary'
    \| 'alarm'
    \| 'critical'
    \| 'warning'
    \| 'info'
    \| 'neutral'
    \| 'success'
    \| 'custom'` | `'primary'` |  | Pill variant |

### `IxPopoverContent` (`<ix-popover-content>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `noPadding` | `boolean` | `false` | 5.1.0 | Remove default inner padding. |

### `IxPopoverFooter` (`<ix-popover-footer>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `alignment` | `'horizontal' \| 'vertical'` | `'horizontal'` | 5.1.0 | Button layout direction |

### `IxPopoverImage` (`<ix-popover-image>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `image?` | `string` |  | 5.1.0 | Image source URL |
| `imageAlt` | `string` | `''` | 5.1.0 | Alt text for the image. Use an empty string for decorative images; provide descriptive text for content images. |

### `IxProgressIndicator` (`<ix-progress-indicator>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `helperText?` | `string` |  |  | The helper text for the progress indicator. |
| `label?` | `string` |  |  | The label for the progress indicator. |
| `max` | `number` | `100` |  | The maximum value of the progress indicator. |
| `min` | `number` | `0` |  | The minimum value of the progress indicator. |
| `showTextAsTooltip` | `boolean` | `false` |  | Show the helper text as a tooltip |
| `size` | `ProgressIndicatorSize` | `'md'` |  | The size of the progress indicator. |
| `status` | `ProgressIndicatorStatus` | `'default'` |  | The state of the progress indicator. This is used to indicate the current state of the progress indicator. |
| `textAlignment` | `'left' \| 'center' \| 'right'` | `'left'` |  | The text alignment for the helper text. Can be 'left', 'center', or 'right'. |
| `type` | `'linear' \| 'circular'` | `'linear'` |  | The type of progress indicator to use. |
| `value` | `number` | `0` |  | The value of the progress indicator. |

### `IxPushCard` (`<ix-push-card>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `ariaLabelIcon?` | `string` |  | 3.2.0 | ARIA label for the icon |
| `expanded` | `boolean` | `false` |  | Expand the card |
| `heading?` | `string` |  |  | Card heading |
| `icon?` | `string` |  |  | Card icon |
| `notification?` | `string` |  |  | Card KPI value |
| `passive` | `boolean` | `false` |  | If true, disables hover and active styles and changes cursor to default |
| `subheading?` | `string` |  |  | Card subheading |
| `variant` | `PushCardVariant` | `'outline'` |  | Card variant |

### `IxRangeField` (`<ix-range-field>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `hideArrow` | `boolean` | `false` |  | Hides the arrow icon between the two input fields. This can be used when the input range is used in a context where the arrow icon is not desired, such as in a form field with a custom label. |
| `type?` | `'time-range' \| 'date-range' \| 'datetime-range'` |  |  | The type of the input range. If set to "time-range", the input range will be displayed as a time range. |

### `IxToastContainer` (`<ix-toast-container>`)

| Prop | Type | Default | Since | Notes |
|---|---|---|---|---|
| `position` | `'bottom-right' \| 'top-right'` | `'bottom-right'` |  | Position of the toast container. Determines where the toasts will be displayed on the screen. |
| `showToast` | `(config: ToastConfig) => Promise<ShowToastResult>` |  |  | Display a toast message @param config |

