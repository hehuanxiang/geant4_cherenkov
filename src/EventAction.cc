//
// EventAction.cc
//

#include "EventAction.hh"
#include "RunAction.hh"

#include "G4Event.hh"
#include "G4PrimaryVertex.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"

std::atomic<G4int> EventAction::fTotalPhotonCount(0);
std::atomic<long> EventAction::fDoseDepositsWithoutPrimary(0);

EventAction::EventAction(RunAction* runAction)
: G4UserEventAction(),
  fRunAction(runAction)
{}

EventAction::~EventAction()
{}

void EventAction::BeginOfEventAction(const G4Event* event)
{
  fPhotonDataMap.clear();

  G4PrimaryVertex* pv = event->GetPrimaryVertex(0);
  if (pv) {
    G4ThreeVector pos = pv->GetPosition();
    fPrimaryVertexX = pos.x() / cm;
    fPrimaryVertexY = pos.y() / cm;
    fPrimaryVertexZ = pos.z() / cm;
    fHasPrimaryVertex = true;
  } else {
    fPrimaryVertexX = fPrimaryVertexY = fPrimaryVertexZ = 0.0;
    fHasPrimaryVertex = false;
  }
  fCurrentEventId = event->GetEventID();
}

void EventAction::EndOfEventAction(const G4Event*)
{   
  // Write out all complete photon data
  for (const auto& pair : fPhotonDataMap) {
    const PhotonData& data = pair.second;
    if (data.hasData) {
      fRunAction->RecordPhotonData(
        data.initialX, data.initialY, data.initialZ,
        data.initialDirX, data.initialDirY, data.initialDirZ,
        data.finalX, data.finalY, data.finalZ,
        data.finalDirX, data.finalDirY, data.finalDirZ,
        data.finalEnergy, fCurrentEventId, pair.first
      );
    }
  }
}

void EventAction::RecordPhotonCreation(G4int trackID, G4double x, G4double y, G4double z,
                                       G4double dirx, G4double diry, G4double dirz)
{
  fTotalPhotonCount.fetch_add(1);  // 原子递增，MT 安全
  
  PhotonData& data = fPhotonDataMap[trackID];
  data.initialX = x;
  data.initialY = y;
  data.initialZ = z;
  data.initialDirX = dirx;
  data.initialDirY = diry;
  data.initialDirZ = dirz;
  data.hasData = false;
}

void EventAction::RecordPhotonEnd(G4int trackID, G4double x, G4double y, G4double z,
                                  G4double dirx, G4double diry, G4double dirz, G4double energy)
{
  auto it = fPhotonDataMap.find(trackID);
  if (it != fPhotonDataMap.end()) {
    PhotonData& data = it->second;
    data.finalX = x;
    data.finalY = y;
    data.finalZ = z;
    data.finalDirX = dirx;
    data.finalDirY = diry;
    data.finalDirZ = dirz;
    data.finalEnergy = energy;
    data.hasData = true;
  }
}

void EventAction::RecordDoseData(G4double x, G4double y, G4double z, G4double energy, G4int pdg)
{
  G4double x_cm = x / cm;
  G4double y_cm = y / cm;
  G4double z_cm = z / cm;
  G4double dx = 0.0, dy = 0.0, dz = 0.0;
  if (fHasPrimaryVertex) {
    dx = x_cm - fPrimaryVertexX;
    dy = y_cm - fPrimaryVertexY;
    dz = z_cm - fPrimaryVertexZ;
  } else {
    fDoseDepositsWithoutPrimary.fetch_add(1);
  }
  fRunAction->RecordDoseData(x_cm, y_cm, z_cm, dx, dy, dz, energy, fCurrentEventId, pdg);
}
