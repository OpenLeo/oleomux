#include "307.h"

void ole07_parse_commandes_bsi(can_msg* msg, ole07_commandes_bsi* ptr) {

    ptr->NUM_PROF_1 = (((msg->data[0]) & 0b11000000) >> 6);
    ptr->RAPP_MEM_C = (((msg->data[0]) & 0b00100000) >> 5);
    ptr->MISE_MEM_C = (((msg->data[0]) & 0b00010000) >> 4);
    ptr->NUM_MEM_C = (((msg->data[0]) & 0b00001111);
    ptr->NUM_PROF_2 = (((msg->data[1]) & 0b11000000) >> 6);
    ptr->RAPP_MEM_P = (((msg->data[1]) & 0b00100000) >> 5);
    ptr->MISE_MEM_P = (((msg->data[1]) & 0b00010000) >> 4);
    ptr->NUM_MEM_P = (((msg->data[1]) & 0b00001111);
    ptr->MODE_ECO = (((msg->data[2]) & 0b10000000) >> 7);
    ptr->NIV_DELEST = (((msg->data[2]) & 0b00001111);
    ptr->RESYNC = (((msg->data[3]) & 0b10000000) >> 7);
    ptr->TYPE_RHEOS = (((msg->data[3]) & 0b01000000) >> 6);
    ptr->ETAT_JN = (((msg->data[3]) & 0b00100000) >> 5);
    ptr->BCK_PNL = (((msg->data[3]) & 0b00010000) >> 4);
    ptr->LUMINOSITE = (((msg->data[3]) & 0b00001111);
    ptr->DEM_EFFAC_DEF = (((msg->data[4]) & 0b01000000) >> 6);
    ptr->DIAG_MUX_ON = (((msg->data[4]) & 0b00100000) >> 5);
    ptr->INTERD_MEMO_DEF = (((msg->data[4]) & 0b00001000) >> 3);
    ptr->PHASE_VIE = (((msg->data[4]) & 0b00000111);
    ptr->ETAT_GMP_HY = (((msg->data[5]) & 0b11100000) >> 5);
    ptr->UB_ETAT_GMP_HY = (((msg->data[5]) & 0b00010000) >> 4);
    ptr->MODE_HY = (((msg->data[5]) & 0b00001110) >> 1);
    ptr->UB_MODE_HY = (((msg->data[5]) & 0b00000001);
    ptr->ETAT_ACTIVATION_AVR = (((msg->data[6]) & 0b00001000) >> 3);
    ptr->ON_OFF_RAD = (((msg->data[6]) & 0b00000010) >> 1);
    ptr->SYNC_ON_OFF_RAD = (((msg->data[6]) & 0b00000001);
    ptr->SECU_ETAT_SEV = (((msg->data[7]) & 0b11110000) >> 4);
    ptr->INVIOLABILITE_AUDIO = (((msg->data[7]) & 0b00000010) >> 1);
    ptr->POSITION_TE = (((msg->data[7]) & 0b00000001);
}

void ole07_parse_donnees_bsi_rapides(can_msg* msg, ole07_donnees_bsi_rapides* ptr) {

    ptr->VITM = (((msg->data[0] << 8 | msg->data[1]))) * 0.125;
    ptr->VITV = (((msg->data[2] << 8 | msg->data[3]))) * 0.01;
    ptr->DIST = (((msg->data[4] << 8 | msg->data[5]))) * 0.1;
    ptr->CONSO = (((msg->data[6]))) * 80;
    ptr->SECU_VITV = (((msg->data[7]) & 0b10000000) >> 7);
    ptr->SECU_VITESSE = (((msg->data[7]) & 0b01111000) >> 3);
}

void ole07_parse_donnees_bsi_lentes(can_msg* msg, ole07_donnees_bsi_lentes* ptr) {

    ptr->MDE_CFG = (((msg->data[0]) & 0b11000000) >> 6);
    ptr->PARC_USINE = (((msg->data[0]) & 0b00100000) >> 5);
    ptr->ETAT_PRINCIP_SEV = (((msg->data[0]) & 0b00011000) >> 3);
    ptr->ETAT_GEN = (((msg->data[0]) & 0b00000100) >> 2);
    ptr->ETAT_GMP = (((msg->data[0]) & 0b00000011);
    ptr->TEAU = (((msg->data[1]))) - 40;
    ptr->KM_TOTAL = (((msg->data[2] << 16 | msg->data[3] << 8 | msg->data[4]))) * 0.1;
    ptr->T_EXT = (((msg->data[5]))) * 0.5 - 40;
    ptr->T_EXT_FILT = (((msg->data[6]))) * 0.5 - 40;
    ptr->ETAT_MA = (((msg->data[7]) & 0b10000000) >> 7);
    ptr->ESSUYAGE = (((msg->data[7]) & 0b01000000) >> 6);
    ptr->TYPE_DIR = (((msg->data[7]) & 0b00110000) >> 4);
    ptr->TEST_VOY_CMB = (((msg->data[7]) & 0b00001000) >> 3);
    ptr->CONTACT_FREIN1 = (((msg->data[7]) & 0b00000100) >> 2);
    ptr->ETAT_CLIGNOTANTS = (((msg->data[7]) & 0b00000011);
}

