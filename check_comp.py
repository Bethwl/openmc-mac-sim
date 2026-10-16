M = {"Li": 6.941, "B": 10.811, "O": 15.9994, "Al": 26.9815, "Si": 28.0855, "Ca": 40.078, "Gd": 157.25}

M_B2O3  = 2*M["B"] + 3*M["O"]
M_SiO2  = M["Si"] + 2*M["O"]
M_Li2O  = 2*M["Li"] + M["O"]
M_Al2O3 = 2*M["Al"] + 3*M["O"]
M_Gd2O3 = 2*M["Gd"] + 3*M["O"]
M_CaO   = M["Ca"] + M["O"]

glasses = {
    "S1": {"B2O3": 45, "SiO2": 10, "Li2O": 40, "Al2O3": 5,  "Gd2O3": 0,  "CaO": 0},
    "S2": {"B2O3": 40, "SiO2": 10, "Li2O": 40, "Al2O3": 5,  "Gd2O3": 5,  "CaO": 0},
    "S3": {"B2O3": 35, "SiO2": 10, "Li2O": 40, "Al2O3": 5,  "Gd2O3": 10, "CaO": 0},
    "S4": {"B2O3": 30, "SiO2": 10, "Li2O": 40, "Al2O3": 5,  "Gd2O3": 15, "CaO": 0},
    "S5": {"B2O3": 60, "SiO2": 10, "Li2O": 0,  "Al2O3": 0,  "Gd2O3": 20, "CaO": 10},
    "S6": {"B2O3": 55, "SiO2": 10, "Li2O": 0,  "Al2O3": 0,  "Gd2O3": 25, "CaO": 10},
    "S7": {"B2O3": 50, "SiO2": 10, "Li2O": 0,  "Al2O3": 0,  "Gd2O3": 30, "CaO": 10},
    "S8": {"B2O3": 45, "SiO2": 10, "Li2O": 0,  "Al2O3": 0,  "Gd2O3": 35, "CaO": 10},
}

densities = {"S1": 2.390, "S2": 2.725, "S3": 2.908, "S4": 3.103, "S5": 3.836, "S6": 3.909, "S7": 4.181, "S8": 4.411}

print("=== EXACT CHEMICAL COMPOSITION TABLE (wt fraction) ===")
for name, comp in glasses.items():
    tot = (comp["B2O3"]*M_B2O3 + comp["SiO2"]*M_SiO2 + comp["Li2O"]*M_Li2O +
           comp["Al2O3"]*M_Al2O3 + comp["Gd2O3"]*M_Gd2O3 + comp["CaO"]*M_CaO)
    
    w_Li = comp["Li2O"] * 2 * M["Li"] / tot
    w_B  = comp["B2O3"] * 2 * M["B"] / tot
    w_O  = (comp["B2O3"]*3 + comp["SiO2"]*2 + comp["Li2O"]*1 + comp["Al2O3"]*3 + comp["Gd2O3"]*3 + comp["CaO"]*1) * M["O"] / tot
    w_Al = comp["Al2O3"] * 2 * M["Al"] / tot
    w_Si = comp["SiO2"] * 1 * M["Si"] / tot
    w_Ca = comp["CaO"] * 1 * M["Ca"] / tot
    w_Gd = comp["Gd2O3"] * 2 * M["Gd"] / tot
    s = w_Li + w_B + w_O + w_Al + w_Si + w_Ca + w_Gd
    print(f"{name}: rho={densities[name]}, Li={w_Li:.5f}, B={w_B:.5f}, O={w_O:.5f}, Al={w_Al:.5f}, Si={w_Si:.5f}, Ca={w_Ca:.5f}, Gd={w_Gd:.5f} (Sum={s:.5f})")
