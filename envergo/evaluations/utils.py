import re


def extract_postal_code(address):
    """Extract french postal code from a stringified address.
    return None if no postal code is found.
    """
    # Regular expression pattern to match postal codes in the correct context
    postal_code_pattern = re.compile(r"\b\d{5}(?!\d)\b")
    matches = postal_code_pattern.findall(address)
    if matches:
        # Returning the last found postal code (in case of multiple matches)
        return matches[-1]
    return None


def extract_department(address):
    """Extract the department as two (or three) digits from a stringified address.
    return None if no department is found.
    """
    postal_code = extract_postal_code(address)
    department = None
    if postal_code:
        department = postal_code[:2]
        if department == "97":
            # for overseas departments, we need the 3 first digits
            department = postal_code[:3]

        if postal_code.startswith("20"):
            # Corsica postal codes are special cases
            code_number = int(postal_code)
            if 20000 <= code_number <= 20190:
                department = "2A"  # Corse-du-Sud
            elif 20200 <= code_number <= 20620:
                department = "2B"  # Haute-Corse

    return department
