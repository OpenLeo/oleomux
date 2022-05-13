typedef struct ole07_commandes_bsi{
    uint8_t NUM_PROF_1;
    uint8_t RAPP_MEM_C;
    uint8_t MISE_MEM_C;
    uint8_t NUM_MEM_C;
    uint8_t NUM_PROF_2;
    uint8_t RAPP_MEM_P;
    uint8_t MISE_MEM_P;
    uint8_t NUM_MEM_P;
    uint8_t MODE_ECO;
    uint8_t NIV_DELEST;
    uint8_t RESYNC;
    uint8_t TYPE_RHEOS;
    uint8_t ETAT_JN;
    uint8_t BCK_PNL;
    uint8_t LUMINOSITE;
    uint8_t DEM_EFFAC_DEF;
    uint8_t DIAG_MUX_ON;
    uint8_t INTERD_MEMO_DEF;
    uint8_t PHASE_VIE;
    uint8_t ETAT_GMP_HY;
    uint8_t UB_ETAT_GMP_HY;
    uint8_t MODE_HY;
    uint8_t UB_MODE_HY;
    uint8_t ETAT_ACTIVATION_AVR;
    uint8_t ON_OFF_RAD;
    uint8_t SYNC_ON_OFF_RAD;
    uint8_t SECU_ETAT_SEV;
    uint8_t INVIOLABILITE_AUDIO;
    uint8_t POSITION_TE;
} ole07_commandes_bsi; 

typedef struct ole07_donnees_bsi_rapides{
    uint16_t VITM;
    uint16_t VITV;
    uint16_t DIST;
    uint8_t SECU_VITV;
    uint8_t SECU_VITESSE;
} ole07_donnees_bsi_rapides; 

typedef struct ole07_donnees_bsi_lentes{
    uint8_t MDE_CFG;
    uint8_t PARC_USINE;
    uint8_t ETAT_PRINCIP_SEV;
    uint8_t ETAT_GEN;
    uint8_t ETAT_GMP;
    uint32_t KM_TOTAL;
    uint8_t ETAT_MA;
    uint8_t ESSUYAGE;
    uint8_t TYPE_DIR;
    uint8_t TEST_VOY_CMB;
    uint8_t CONTACT_FREIN1;
    uint8_t ETAT_CLIGNOTANTS;
} ole07_donnees_bsi_lentes; 

