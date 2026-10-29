/*
 * TP RCSF - Clustering LEACH sous NS3
 * Modèle radio de premier ordre (Heinzelman et al.), simulation par rounds.
 *
 * Utilisation (depuis ~/ns3) :
 *   ./ns3 run "scratch/leach --n=100 --run=1 --out=results/leach_n100_run1.csv"
 *
 * Colonnes du CSV (une ligne par round) :
 *   round, total_energy, alive, nCH, data_sent, data_recv, ctrl_msgs,
 *   setup_time, mean_energy_alive, mean_energy_CH
 *   (data_sent, data_recv et ctrl_msgs sont CUMULATIFS ; setup_time est celui du round)
 */
#include "ns3/core-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace ns3;

// ---------------- Modèle radio de premier ordre ----------------
static const double E_ELEC = 50e-9;       // J/bit
static const double E_FS = 10e-12;        // J/bit/m^2
static const double E_MP = 0.0013e-12;    // J/bit/m^4  (pJ ! voir le guide, remarque d'unité)
static const double E_DA = 5e-9;          // J/bit/signal (agrégation)
static const double D0 = std::sqrt(E_FS / E_MP); // ~87.7 m

static double
TxE(uint32_t bits, double d)
{
    return E_ELEC * bits + (d < D0 ? E_FS * bits * d * d : E_MP * bits * d * d * d * d);
}

static double
RxE(uint32_t bits)
{
    return E_ELEC * bits;
}

struct Sensor
{
    double e;
    int lastEpoch; // dernière époque où le noeud a été CH (-1 : jamais)
    bool alive;
};

class LeachSim
{
  public:
    LeachSim(uint32_t n,
             uint32_t rounds,
             double p,
             uint32_t kData,
             uint32_t kCtrl,
             double e0,
             double per,
             double area,
             double bsx,
             double bsy,
             double advRange,
             std::string csv);
    void Run();

  private:
    void StartRound();
    void ElectCH();
    void FormClusters();
    void SteadyState();
    void Record();
    double D(uint32_t i, uint32_t j) const;
    double DBS(uint32_t i) const;
    bool Spend(uint32_t i, double joules);

    NodeContainer m_nodes;
    Vector m_bs;
    std::vector<Sensor> m_s;
    std::vector<bool> m_isCH;
    std::vector<uint32_t> m_ch;
    std::vector<int> m_head; // CH du noeud (-1 : envoi direct à la BS)
    uint32_t m_n;
    uint32_t m_rounds;
    uint32_t m_r{0};
    uint32_t m_kD;
    uint32_t m_kC;
    double m_p;
    double m_per;
    double m_advRange;
    double m_setup{0};
    uint64_t m_sent{0};
    uint64_t m_recv{0};
    uint64_t m_ctrl{0};
    int m_fnd{-1};
    int m_hnd{-1};
    int m_lnd{-1};
    const double m_bitrate{250e3}; // 250 kbit/s (IEEE 802.15.4)
    const double m_roundDur{1.0};  // 1 round = 1 s simulée
    Ptr<UniformRandomVariable> m_rng;
    std::vector<Vector> m_pos;
    std::ofstream m_out;
};

LeachSim::LeachSim(uint32_t n,
                   uint32_t rounds,
                   double p,
                   uint32_t kData,
                   uint32_t kCtrl,
                   double e0,
                   double per,
                   double area,
                   double bsx,
                   double bsy,
                   double advRange,
                   std::string csv)
    : m_bs(bsx, bsy, 0),
      m_n(n),
      m_rounds(rounds),
      m_kD(kData),
      m_kC(kCtrl),
      m_p(p),
      m_per(per),
      m_advRange(advRange)
{
    m_nodes.Create(n);

    // Positions aléatoires fixes dans area x area
    Ptr<UniformRandomVariable> u = CreateObject<UniformRandomVariable>();
    u->SetAttribute("Min", DoubleValue(0.0));
    u->SetAttribute("Max", DoubleValue(area));
    Ptr<RandomRectanglePositionAllocator> alloc = CreateObject<RandomRectanglePositionAllocator>();
    alloc->SetX(u);
    alloc->SetY(u);
    MobilityHelper mob;
    mob.SetPositionAllocator(alloc);
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(m_nodes);

    // Positions mises en cache (évite des GetObject répétés)
    for (uint32_t i = 0; i < n; i++)
    {
        m_pos.push_back(m_nodes.Get(i)->GetObject<MobilityModel>()->GetPosition());
    }

    m_s.assign(n, Sensor{e0, -1, true});
    m_head.assign(n, -1);
    m_isCH.assign(n, false);
    m_rng = CreateObject<UniformRandomVariable>();

    m_out.open(csv);
    if (!m_out.is_open())
    {
        NS_FATAL_ERROR("Impossible d'ouvrir " << csv << " (le dossier existe-t-il ?)");
    }
    m_out << "round,total_energy,alive,nCH,data_sent,data_recv,ctrl_msgs,setup_time,"
             "mean_energy_alive,mean_energy_CH\n";
}

double
LeachSim::D(uint32_t i, uint32_t j) const
{
    return std::hypot(m_pos[i].x - m_pos[j].x, m_pos[i].y - m_pos[j].y);
}

double
LeachSim::DBS(uint32_t i) const
{
    return std::hypot(m_pos[i].x - m_bs.x, m_pos[i].y - m_bs.y);
}

// Retire l'énergie ; renvoie false si le noeud est mort ou n'a pas assez d'énergie.
bool
LeachSim::Spend(uint32_t i, double joules)
{
    if (!m_s[i].alive)
    {
        return false;
    }
    if (m_s[i].e < joules)
    {
        m_s[i].e = 0;
        m_s[i].alive = false;
        return false;
    }
    m_s[i].e -= joules;
    if (m_s[i].e <= 0)
    {
        m_s[i].e = 0;
        m_s[i].alive = false;
    }
    return true;
}

void
LeachSim::ElectCH()
{
    m_ch.clear();
    std::fill(m_isCH.begin(), m_isCH.end(), false);
    // Époque = 1/p rounds (20 pour p = 0,05). Au début de chaque époque, tous les noeuds redeviennent
    // éligibles ; un noeud déjà CH dans l'époque courante ne peut plus l'être (ensemble G de LEACH).
    const int period = (int)std::round(1.0 / m_p);
    const int epoch = (int)m_r / period;
    const double T = m_p / (1.0 - m_p * (double)(m_r % period));
    for (uint32_t i = 0; i < m_n; i++)
    {
        if (!m_s[i].alive)
        {
            continue;
        }
        const bool eligible = m_s[i].lastEpoch < epoch;
        if (eligible && m_rng->GetValue() < T)
        {
            m_ch.push_back(i);
            m_isCH[i] = true;
            m_s[i].lastEpoch = epoch;
        }
    }
}

void
LeachSim::FormClusters()
{
    std::fill(m_head.begin(), m_head.end(), -1);
    const uint32_t nCH = m_ch.size();
    const double tCtrl = m_kC / m_bitrate;

    // 1) ADV : chaque CH diffuse ; tous les non-CH vivants écoutent
    for (uint32_t c : m_ch)
    {
        Spend(c, TxE(m_kC, m_advRange));
        m_ctrl++;
        for (uint32_t i = 0; i < m_n; i++)
        {
            if (m_s[i].alive && !m_isCH[i])
            {
                Spend(i, RxE(m_kC));
            }
        }
    }

    // 2) JOIN : chaque non-CH rejoint le CH (vivant) le plus proche
    std::vector<uint32_t> members(m_n, 0);
    for (uint32_t i = 0; i < m_n; i++)
    {
        if (!m_s[i].alive || m_isCH[i] || nCH == 0)
        {
            continue;
        }
        int best = -1;
        double dmin = 1e18;
        for (uint32_t c : m_ch)
        {
            if (m_s[c].alive && D(i, c) < dmin)
            {
                dmin = D(i, c);
                best = (int)c;
            }
        }
        if (best < 0)
        {
            continue;
        }
        m_head[i] = best;
        members[best]++;
        Spend(i, TxE(m_kC, dmin));
        Spend(best, RxE(m_kC));
        m_ctrl++;
    }

    // 3) SCHEDULE TDMA : un message par CH
    for (uint32_t c : m_ch)
    {
        Spend(c, TxE(m_kC, m_advRange));
        m_ctrl++;
    }

    // Temps de setup : ADV (CH en séquence) + JOIN (sérialisés par CH, le plus chargé) + SCHEDULE
    uint32_t maxMembers = 0;
    for (uint32_t c : m_ch)
    {
        maxMembers = std::max(maxMembers, members[c]);
    }
    m_setup = (nCH + maxMembers + nCH) * tCtrl;
}

void
LeachSim::SteadyState()
{
    std::vector<uint32_t> got(m_n, 0);

    // Membres -> CH (ou -> BS en repli)
    for (uint32_t i = 0; i < m_n; i++)
    {
        if (!m_s[i].alive || m_isCH[i])
        {
            continue;
        }
        const double d = (m_head[i] >= 0) ? D(i, m_head[i]) : DBS(i);
        if (!Spend(i, TxE(m_kD, d)))
        {
            continue; // plus assez d'énergie : le paquet n'est pas émis
        }
        m_sent++;
        const bool lost = m_rng->GetValue() < m_per;
        if (m_head[i] < 0)
        {
            if (!lost)
            {
                m_recv++;
            }
            continue;
        }
        const uint32_t c = m_head[i];
        if (!lost && m_s[c].alive && Spend(c, RxE(m_kD)))
        {
            got[c]++;
        }
    }

    // CH : agrégation puis un paquet vers la BS
    for (uint32_t c : m_ch)
    {
        if (!m_s[c].alive)
        {
            continue;
        }
        m_sent++; // donnée propre du CH
        const uint32_t signals = got[c] + 1;
        Spend(c, E_DA * m_kD * signals);
        if (Spend(c, TxE(m_kD, DBS(c))) && m_rng->GetValue() >= m_per)
        {
            m_recv += signals; // on compte les paquets sources livrés
        }
    }
}

void
LeachSim::Record()
{
    double tot = 0;
    uint32_t alive = 0;
    for (const auto& s : m_s)
    {
        tot += s.e;
        if (s.alive)
        {
            alive++;
        }
    }
    double chE = 0;
    for (uint32_t c : m_ch)
    {
        chE += m_s[c].e;
    }
    const double meanChE = m_ch.empty() ? 0.0 : chE / m_ch.size();
    const double meanAlive = alive ? tot / alive : 0.0;

    if (m_fnd < 0 && alive < m_n)
    {
        m_fnd = (int)m_r + 1;
    }
    if (m_hnd < 0 && alive <= m_n / 2)
    {
        m_hnd = (int)m_r + 1;
    }
    if (m_lnd < 0 && alive == 0)
    {
        m_lnd = (int)m_r + 1;
    }

    m_out << m_r << "," << tot << "," << alive << "," << m_ch.size() << "," << m_sent << ","
          << m_recv << "," << m_ctrl << "," << m_setup << "," << meanAlive << "," << meanChE
          << "\n";
}

void
LeachSim::StartRound()
{
    ElectCH();
    FormClusters();
    SteadyState();
    Record();
    m_r++;
    if (m_r < m_rounds)
    {
        Simulator::Schedule(Seconds(m_roundDur), &LeachSim::StartRound, this);
    }
}

void
LeachSim::Run()
{
    Simulator::Schedule(Seconds(0), &LeachSim::StartRound, this);
    Simulator::Run();
    Simulator::Destroy();
    m_out.close();
    std::cout << "FND=" << m_fnd << " HND=" << m_hnd << " LND=" << m_lnd
              << " data_sent=" << m_sent << " data_recv=" << m_recv << " PDR="
              << (m_sent ? (double)m_recv / m_sent : 0.0) << std::endl;
}

int
main(int argc, char* argv[])
{
    uint32_t n = 100;
    uint32_t rounds = 1000;
    uint32_t run = 1;
    uint32_t kData = 4000;
    uint32_t kCtrl = 200;
    double p = 0.05;
    double e0 = 0.5;
    double per = 0.0;
    double area = 200.0;
    double bsx = 100.0;
    double bsy = 250.0;
    double advRange = 100.0;
    std::string out = "results/leach.csv";

    CommandLine cmd(__FILE__);
    cmd.AddValue("n", "Nombre de noeuds", n);
    cmd.AddValue("rounds", "Nombre de rounds", rounds);
    cmd.AddValue("run", "Numero de graine (RngRun)", run);
    cmd.AddValue("p", "Proportion de CH", p);
    cmd.AddValue("kData", "Bits d'un paquet de donnees", kData);
    cmd.AddValue("kCtrl", "Bits d'un paquet de controle", kCtrl);
    cmd.AddValue("e0", "Energie initiale (J)", e0);
    cmd.AddValue("per", "Taux de perte aleatoire (0 = canal ideal)", per);
    cmd.AddValue("area", "Cote de la zone carree (m)", area);
    cmd.AddValue("bsx", "Abscisse de la BS", bsx);
    cmd.AddValue("bsy", "Ordonnee de la BS", bsy);
    cmd.AddValue("advRange", "Portee des messages ADV/SCHEDULE (m)", advRange);
    cmd.AddValue("out", "Fichier CSV de sortie", out);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(12345);
    RngSeedManager::SetRun(run);

    LeachSim sim(n, rounds, p, kData, kCtrl, e0, per, area, bsx, bsy, advRange, out);
    sim.Run();
    return 0;
}
