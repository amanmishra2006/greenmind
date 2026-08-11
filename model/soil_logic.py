def classify_ph(ph):
    if ph < 5.5:
        return "Strongly Acidic", "Recommend soil testing and gradual liming where appropriate. Avoid blindly increasing fertilizer dosage."
    elif ph < 6.0:
        return "Slightly Acidic", "Recommend monitoring pH and using crop-appropriate amendments."
    elif ph <= 7.5:
        return "Suitable / Near Ideal", "pH is in a good range for most crops. Maintain current soil management."
    elif ph <= 8.0:
        return "Slightly Alkaline", "Recommend adding organic matter and crop-specific nutrient management."
    else:
        return "Strongly Alkaline", "Recommend professional soil testing and suitable soil amendments."


def classify_nutrient(value, low_max, high_min, name):
    if value < low_max:
        return "Low"
    elif value > high_min:
        return "High"
    else:
        return "Adequate"


def soil_type_advice(soil_type):
    advice = {
        "Sandy": "Sandy soil drains water quickly and nutrients can leach fast. Add compost/organic matter and prefer smaller, split fertilizer applications.",
        "Loamy": "Loamy soil generally has a good balance of drainage and nutrient retention. Fertilize mainly based on N-P-K deficiency.",
        "Clayey": "Clayey soil holds water and nutrients strongly, with risk of waterlogging. Ensure good drainage, avoid excess irrigation, and add organic matter to improve structure.",
        "Silty": "Silty soil is generally fertile but can become compacted. Add organic matter and ensure proper drainage."
    }
    return advice.get(soil_type, "")


def analyze_soil(soil_type, ph, nitrogen, phosphorus, potassium, moisture, organic_matter):
    recommendations = []

    # Soil type
    recommendations.append({
        "problem": f"Soil Type: {soil_type}",
        "cause": "-",
        "action": soil_type_advice(soil_type),
        "reason": "Soil type affects water retention, drainage, and nutrient availability."
    })

    # pH
    ph_status, ph_advice = classify_ph(ph)
    recommendations.append({
        "problem": f"pH Level: {ph} ({ph_status})",
        "cause": "Naturally occurring soil chemistry or long-term fertilizer/irrigation practices.",
        "action": ph_advice,
        "reason": "pH affects how well plant roots can absorb nutrients."
    })

    # Nitrogen
    n_status = classify_nutrient(nitrogen, 280, 560, "Nitrogen")
    if n_status == "Low":
        recommendations.append({
            "problem": f"Nitrogen: {nitrogen} kg/ha (Low)",
            "cause": "Possible Nitrogen Deficiency — often due to leaching, low organic matter, or heavy previous cropping.",
            "action": "Consider a nitrogen-rich fertilizer such as urea, or organic nitrogen sources like compost.",
            "reason": "Nitrogen is essential for leaf growth and overall plant vigor."
        })
    elif n_status == "High":
        recommendations.append({
            "problem": f"Nitrogen: {nitrogen} kg/ha (High)",
            "cause": "Possible over-fertilization with nitrogen in the past.",
            "action": "Avoid applying additional nitrogen fertilizer for now.",
            "reason": "Excess nitrogen can cause excessive leafy growth and delay fruiting, and can leach into groundwater."
        })

    # Phosphorus
    p_status = classify_nutrient(phosphorus, 10, 25, "Phosphorus")
    if p_status == "Low":
        recommendations.append({
            "problem": f"Phosphorus: {phosphorus} kg/ha (Low)",
            "cause": "Possible Phosphorus Deficiency — common in acidic or heavily leached soils.",
            "action": "Consider phosphorus-containing fertilizer such as SSP or DAP, depending on the crop.",
            "reason": "Phosphorus supports root development and flowering/fruiting."
        })
    elif p_status == "High":
        recommendations.append({
            "problem": f"Phosphorus: {phosphorus} kg/ha (High)",
            "cause": "Possible over-fertilization with phosphorus.",
            "action": "Avoid applying additional phosphorus fertilizer unnecessarily.",
            "reason": "Excess phosphorus can block uptake of other nutrients like zinc and iron."
        })

    # Potassium
    k_status = classify_nutrient(potassium, 110, 280, "Potassium")
    if k_status == "Low":
        recommendations.append({
            "problem": f"Potassium: {potassium} kg/ha (Low)",
            "cause": "Possible Potassium Deficiency — common in sandy or heavily cropped soils.",
            "action": "Consider potassium fertilizer such as MOP or SOP, depending on crop suitability.",
            "reason": "Potassium improves disease resistance, water regulation, and fruit quality."
        })
    elif k_status == "High":
        recommendations.append({
            "problem": f"Potassium: {potassium} kg/ha (High)",
            "cause": "Possible over-fertilization with potassium.",
            "action": "Avoid applying additional potassium fertilizer unnecessarily.",
            "reason": "Excess potassium can interfere with magnesium and calcium uptake."
        })

    if n_status == "Adequate" and p_status == "Adequate" and k_status == "Adequate":
        recommendations.append({
            "problem": "N-P-K Levels",
            "cause": "-",
            "action": "N-P-K levels appear balanced. Maintain current nutrient management and monitor the crop.",
            "reason": "Balanced nutrients support healthy, consistent plant growth."
        })

    # Moisture
    if moisture < 20:
        recommendations.append({
            "problem": f"Moisture: {moisture}% (Dry)",
            "cause": "Insufficient irrigation or high evaporation.",
            "action": "Irrigate according to crop requirements. Avoid applying fertilizer to severely dry soil without adequate moisture.",
            "reason": "Dry soil limits nutrient uptake and can stress plant roots."
        })
    elif moisture <= 40:
        recommendations.append({
            "problem": f"Moisture: {moisture}% (Moderate)",
            "cause": "-",
            "action": "Soil moisture is in a healthy, moderate range. Continue current watering routine.",
            "reason": "Balanced moisture supports steady nutrient and water uptake."
        })
    else:
        recommendations.append({
            "problem": f"Moisture: {moisture}% (Wet)",
            "cause": "Overwatering or poor drainage.",
            "action": "Check drainage before irrigating again. Overwatering can cause nutrient leaching and root problems.",
            "reason": "Excess water reduces oxygen available to roots and can lead to root rot."
        })

    # Organic Matter
    if organic_matter < 1.5:
        recommendations.append({
            "problem": f"Organic Matter: {organic_matter}% (Low)",
            "cause": "Limited addition of compost/manure or intensive farming without replenishment.",
            "action": "Add compost, farmyard manure, or other organic matter.",
            "reason": "Organic matter improves soil structure, water retention, and microbial activity."
        })
    elif organic_matter <= 3.5:
        recommendations.append({
            "problem": f"Organic Matter: {organic_matter}% (Reasonable)",
            "cause": "-",
            "action": "Organic matter is at a reasonable level. Continue current practices.",
            "reason": "Adequate organic matter supports long-term soil health."
        })
    else:
        recommendations.append({
            "problem": f"Organic Matter: {organic_matter}% (Good)",
            "cause": "-",
            "action": "Good organic matter level. Maintain current organic matter management.",
            "reason": "High organic matter supports strong microbial activity and nutrient cycling."
        })

    disclaimer = "These are general reference values, not laboratory-certified results. For an exact fertilizer dosage, please provide crop name, growth stage, cultivation area, and prior fertilizer history — ideally combined with a professional soil test."

    return recommendations, disclaimer